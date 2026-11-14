"""
宝藏基质导出 API 路由。

接收前端 Canvas 渲染出的图片，落盘到导出目录，并可选地打开所在文件夹。
"""

import asyncio
import base64
import binascii
import os
import platform
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_exports_dir_dep
from endfield_essence_recognizer.schemas.matrix_export import (
    TreasureMatrixExportRequest,
    TreasureMatrixExportResponse,
    TreasureMatrixTableExportRequest,
)
from endfield_essence_recognizer.services.profile_manager import ProfileManager
from endfield_essence_recognizer.utils.log import logger

router = APIRouter(prefix="/export", tags=["export"])

# 这个接口只接受本工具自己画出来的图，不做通用文件落盘。
# WebP 是 RIFF 容器：前 4 字节 'RIFF'、4 字节长度、再 4 字节 'WEBP'。
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_RIFF_SIGNATURE = b"RIFF"
_WEBP_SIGNATURE = b"WEBP"

# 导出图体积上限。前端 2x 缩放下的实际产物远小于此值，这里只作兜底防御。
_MAX_EXPORT_BYTES = 32 * 1024 * 1024

# Windows 文件名非法字符与控制字符
_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

# 同一秒内同名文件的后缀上限。到上限说明导出目录里堆了上百个同秒文件，
# 此时报错比继续覆盖已有文件更安全。
_MAX_SAME_SECOND_EXPORTS = 100


def _resolve_extension(raw: bytes) -> str:
    """
    按图片魔数确定文件扩展名。

    前端主路径产出 WebP；浏览器不支持 WebP 编码时 canvas.toBlob 会静默回退成
    PNG，两种都要能落盘，否则那种环境下保存会整条失败。扩展名取自实际内容
    而不是前端声明，落盘文件的后缀就一定和内容对得上。

    Args:
        raw: 解码后的图片字节。

    Returns:
        不含点号的扩展名。

    Raises:
        ValueError: 内容既不是 WebP 也不是 PNG。
    """
    if raw[:4] == _RIFF_SIGNATURE and raw[8:12] == _WEBP_SIGNATURE:
        return "webp"
    if raw.startswith(_PNG_SIGNATURE):
        return "png"
    raise ValueError("图片内容不是合法的 WebP 或 PNG")


def _safe_file_stem(profile_name: str) -> str:
    """
    把账号名压成可安全用作文件名的片段。

    账号名允许中文和空格，但可能含有路径分隔符或 Windows 非法字符；
    这里统一替换成下划线并截断，避免写到导出目录之外。

    Args:
        profile_name: 当前激活的账号名称。

    Returns:
        清洗后的文件名主干；账号名清洗后为空时回退为固定值。
    """
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("_", profile_name).strip(" .")
    return cleaned[:32] or "treasure_matrix"


async def _open_directory(directory: Path) -> None:
    """
    在系统文件管理器中打开指定目录。

    Args:
        directory: 需要打开的目录。
    """
    if platform.system() == "Windows":  # Windows
        os.startfile(directory)
    elif platform.system() == "Darwin":  # macOS
        await asyncio.create_subprocess_exec("open", str(directory))
    else:  # Linux and others
        await asyncio.create_subprocess_exec("xdg-open", str(directory))


def _export_file_name(stem_source: str, extension: str, suffix: int = 1) -> str:
    """
    拼导出文件名：账号名清洗后加时间戳，必要时追加序号。

    文件名完全由后端拼接，前端不参与命名，杜绝路径穿越。
    扩展名由调用方从白名单里选定，不接受任意输入。

    Args:
        stem_source: 文件名主干的来源（账号名或调用方指定的主干），会先清洗。
        extension: 不含点号的文件扩展名。
        suffix: 同一秒内的第几个文件；1 表示不追加序号。

    Returns:
        不含目录的文件名。
    """
    stem = _safe_file_stem(stem_source)
    timestamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    if suffix <= 1:
        return f"{stem}_{timestamp}.{extension}"
    return f"{stem}_{timestamp}-{suffix}.{extension}"


def _write_new_export_file(
    exports_dir: Path, stem_source: str, extension: str, payload: bytes
) -> Path:
    """
    以独占方式创建导出文件，返回实际路径。

    时间戳只到秒：同一账号同一秒导出两次（连点两次保存，或图片与表格交替
    导出）会撞出同一个路径。这里用 `open(..., "xb")` 独占创建，撞名就换下
    一个序号，保证已有文件——尤其是导入前备份——不会被悄悄覆盖。

    直接写字节而不是 `write_text`：CSV 已经带 BOM 且用 CRLF 分行，
    字节写入不会经过任何换行符转换。

    Args:
        exports_dir: 导出目录，不存在时会创建。
        stem_source: 文件名主干来源。
        extension: 不含点号的文件扩展名。
        payload: 要写入的字节。

    Returns:
        实际写入的文件路径。

    Raises:
        ValueError: 同一秒内的同名文件超过上限。
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    for suffix in range(1, _MAX_SAME_SECOND_EXPORTS + 1):
        path = exports_dir / _export_file_name(stem_source, extension, suffix)
        try:
            with path.open("xb") as handle:
                handle.write(payload)
        except FileExistsError:
            continue
        return path
    raise ValueError("导出目录里同名文件过多，请先清理导出目录")


async def _open_export_folder(exports_dir: Path, open_folder: bool) -> str | None:
    """
    按需在文件管理器中打开导出目录。

    打开失败不能把「已经落盘成功」报成失败，所以这里只回报错误描述，
    由调用方决定怎么措辞。

    Args:
        exports_dir: 导出目录。
        open_folder: 是否打开。

    Returns:
        无需打开或打开成功时为 None，失败时为错误描述。
    """
    if not open_folder:
        return None
    try:
        await _open_directory(exports_dir)
    except Exception as e:
        logger.exception(f"打开导出目录时出错：{e}")
        return str(e)
    return None


@router.post(
    "/treasure_matrix",
    description="保存宝藏基质导出图片到本地，返回文件路径和文件名",
)
async def export_treasure_matrix(
    request: TreasureMatrixExportRequest,
    exports_dir: Path = Depends(get_exports_dir_dep),
    manager: ProfileManager = Depends(get_profile_manager),
) -> TreasureMatrixExportResponse:
    """接收前端渲染好的图片并落盘，可选地打开所在文件夹。"""
    try:
        try:
            raw = base64.b64decode(request.image_base64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("图片内容不是合法的 base64") from e

        extension = _resolve_extension(raw)

        if len(raw) > _MAX_EXPORT_BYTES:
            raise ValueError(f"图片体积超过上限（{len(raw) / 1024 / 1024:.1f} MB）")

        # 文件名与独占创建都在 _write_new_export_file 里：账号名清洗后加时间戳，
        # 同秒撞名自动追加序号，不会覆盖已有导出或导入前备份。
        save_path = await asyncio.to_thread(
            _write_new_export_file,
            exports_dir,
            manager.get_active_profile_name(),
            extension,
            raw,
        )
        file_name = save_path.name
        logger.info(f"已保存宝藏基质导出图片：{save_path}")

        message = "导出图片已保存。"
        open_failure = await _open_export_folder(exports_dir, request.open_folder)
        if open_failure is not None:
            message = f"导出图片已保存，但打开文件夹失败：{open_failure}"

        return TreasureMatrixExportResponse(
            success=True,
            message=message,
            file_path=str(save_path),
            file_name=file_name,
        )
    except Exception as e:
        logger.exception(f"保存宝藏基质导出图片失败：{e}")
        return TreasureMatrixExportResponse(
            success=False,
            message=str(e),
            file_path=None,
            file_name=None,
        )


@router.post(
    "/treasure_matrix/table",
    description="保存宝藏基质导出表格（CSV/JSON）到本地，返回文件路径和文件名",
)
async def export_treasure_matrix_table(
    request: TreasureMatrixTableExportRequest,
    exports_dir: Path = Depends(get_exports_dir_dep),
    manager: ProfileManager = Depends(get_profile_manager),
) -> TreasureMatrixExportResponse:
    """接收前端序列化好的表格文本并落盘，可选地打开所在文件夹。"""
    try:
        content = request.content
        # 扩展名只取 format 的字面量白名单，客户端无法影响落盘路径
        if request.format == "csv":
            # Excel 只有在文件开头见到 UTF-8 BOM 才按 UTF-8 解析，
            # 否则中文按系统默认编码打开是乱码。JSON 不加，避免解析器把 BOM 当非法字符。
            content = f"\ufeff{content}"

        # 文件名主干由调用方指定时同样要走清洗，前端无法把路径带进来。
        # 写字节而不是 write_text：CSV 已用 CRLF 分行，不能再经过换行符转换。
        save_path = await asyncio.to_thread(
            _write_new_export_file,
            exports_dir,
            request.file_stem or manager.get_active_profile_name(),
            request.format,
            content.encode("utf-8"),
        )
        file_name = save_path.name
        logger.info(f"已保存宝藏基质导出表格：{save_path}")

        message = "导出表格已保存。"
        open_failure = await _open_export_folder(exports_dir, request.open_folder)
        if open_failure is not None:
            message = f"导出表格已保存，但打开文件夹失败：{open_failure}"

        return TreasureMatrixExportResponse(
            success=True,
            message=message,
            file_path=str(save_path),
            file_name=file_name,
        )
    except Exception as e:
        logger.exception(f"保存宝藏基质导出表格失败：{e}")
        return TreasureMatrixExportResponse(
            success=False,
            message=str(e),
            file_path=None,
            file_name=None,
        )
