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

        # 文件名完全由后端拼接：账号名清洗后加时间戳，多次导出天然不覆盖，
        # 前端不参与命名，杜绝路径穿越。
        stem = _safe_file_stem(manager.get_active_profile_name())
        file_name = f"{stem}_{datetime.now():%Y%m%d-%H%M%S}.{extension}"
        save_path = exports_dir / file_name
        await asyncio.to_thread(exports_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(save_path.write_bytes, raw)
        logger.info(f"已保存宝藏基质导出图片：{save_path}")

        message = "导出图片已保存。"
        if request.open_folder:
            # 打开文件夹失败不能把"已经落盘成功"报成失败，降级成提示即可
            try:
                await _open_directory(exports_dir)
            except Exception as e:
                logger.exception(f"打开导出目录时出错：{e}")
                message = f"导出图片已保存，但打开文件夹失败：{e}"

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
