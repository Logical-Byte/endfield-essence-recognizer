"""更新安装模块

基于 manifest.json 实现增量更新：
- 新增：manifest 中有、本地没有的文件 → 复制
- 覆盖：manifest 中有、本地也有的文件 → 覆盖
- 删除：本地有、manifest 中没有、且不在 protected 列表中的文件 → 删除
- protected 保护"删除"和"覆盖"双重语义

manifest.json 存放在 ``_internal/manifest.json``，随更新包一起被复制到目标目录，
下次更新时作为"旧 manifest"被读取。
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from endfield_essence_recognizer.utils.log import logger

UPDATE_TEMP_PARENT_NAME = "endfield-essence-recognizer"
UPDATE_TEMP_PREFIX = "update-"
STALE_UPDATE_TEMP_SECONDS = 24 * 60 * 60

# 清单文件在安装目录中的相对路径（与生成脚本保持一致）
MANIFEST_RELATIVE_PATH = "_internal/manifest.json"

# 增量包元数据只用于 Python 侧安装前校验，不会复制到安装目录。
INCREMENTAL_METADATA_RELATIVE_PATH = "_internal/incremental_update.json"

# Mirror 酱增量包使用的差异描述文件。
MIRROR_CHYAN_CHANGES_RELATIVE_PATH = "changes.json"

# 独立更新器可执行文件名
UPDATER_EXE_NAME = "eer_updater.exe"
UPDATER_RELATIVE_PATH = f"_internal/{UPDATER_EXE_NAME}"

STATUS_DIR_NAME = "logs"

# 运行时只信任这些用户数据路径，避免被篡改的 manifest 保护程序文件。
ALLOWED_PROTECTED_PATHS = {
    "config.json",
    "profiles.json",
    "logs/",
    "screenshots/",
    ".env",
}


def _compute_manifest_sha256(manifest: dict) -> str:
    """计算清单的稳定内容哈希，用于绑定增量包。"""
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _compute_file_sha256(file_path: Path) -> str:
    """计算文件 SHA-256，供 plan 绑定解压后的待复制文件。"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _is_sha256_hex(value: object) -> bool:
    """校验字符串是否是标准 64 位十六进制 SHA-256。"""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdefABCDEF" for ch in value)
    )


def _compute_copy_hashes(
    temp_dir: Path,
    copy_list: list[str],
    manifest: dict | None = None,
) -> dict[str, str]:
    """为 plan 中的复制清单生成兼容式 SHA-256 映射。

    优先使用新版 manifest 的 file_hashes；旧包或 Mirror 酱包缺少该字段时，
    回退为当前解压目录中的实际文件哈希，以防 plan 生成后本地临时文件被改写。
    """
    manifest_hashes = (
        manifest.get("file_hashes", {}) if isinstance(manifest, dict) else {}
    )
    if not isinstance(manifest_hashes, dict):
        manifest_hashes = {}

    copy_hashes: dict[str, str] = {}
    for raw_path in copy_list:
        normalized = raw_path.replace("\\", "/")
        expected_hash = manifest_hashes.get(normalized)
        if _is_sha256_hex(expected_hash):
            copy_hashes[normalized] = str(expected_hash).lower()
            continue

        source_path = temp_dir / normalized
        if source_path.is_file():
            copy_hashes[normalized] = _compute_file_sha256(source_path)

    return copy_hashes


def _is_path_traversal(temp_dir: Path, member: str) -> bool:
    """检查 zip 条目是否存在路径穿越风险。

    使用 Path.relative_to() 做严格的路径归属判断，而非字符串前缀匹配，
    避免前缀碰撞绕过（如 temp_dir="/tmp/u" + member="../update_evil"）。

    Args:
        temp_dir: 解压目标目录（已 resolve）。
        member: zip 条目名称。

    Returns:
        True 表示存在穿越风险，应拒绝该条目。
    """
    resolved_temp = temp_dir.resolve()
    try:
        member_path = (resolved_temp / member).resolve()
        member_path.relative_to(resolved_temp)
        return False
    except ValueError:
        return True


def _load_manifest(temp_dir: Path) -> dict | None:
    """从解压目录中加载 manifest.json。

    读取 ``_internal/manifest.json``（新规范位置），同时兼容根目录 ``manifest.json``
    （旧版更新包回退）。

    Args:
        temp_dir: 解压后的临时目录。

    Returns:
        manifest 字典，如果文件不存在则返回 None。
    """
    # 优先尝试新位置 _internal/manifest.json
    manifest_path = temp_dir / MANIFEST_RELATIVE_PATH
    if not manifest_path.is_file():
        # 回退：旧版更新包把 manifest.json 放在根目录
        manifest_path = temp_dir / "manifest.json"
        if not manifest_path.is_file():
            logger.warning("更新包中未找到 manifest.json，将使用回退方案")
            return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # 基本校验
        if "files" not in manifest or "protected" not in manifest:
            logger.error("manifest.json 格式不完整，缺少 files 或 protected 字段")
            return None
        logger.info(
            f"加载 manifest: version={manifest.get('version', '?')}, "
            f"files={len(manifest['files'])}, protected={len(manifest['protected'])}"
        )
        return manifest
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"加载 manifest.json 失败: {exc}")
        return None


def _safe_status_version(value: object) -> str:
    """将版本号转换为可安全用于状态文件名的片段。"""
    text = str(value or "unknown").strip() or "unknown"
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def _load_installed_manifest_version(current_dir: Path) -> str:
    """从当前已安装的 manifest 中读取版本号。"""
    for manifest_path in (
        current_dir / MANIFEST_RELATIVE_PATH,
        current_dir / "manifest.json",
    ):
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return _safe_status_version(manifest.get("version"))
        except (json.JSONDecodeError, OSError):
            logger.warning(f"无法读取已安装版本: {manifest_path}")
    return "unknown"


def _load_installed_manifest(current_dir: Path) -> dict | None:
    """读取当前已安装的 manifest，供增量包校验基线版本。"""
    for manifest_path in (
        current_dir / MANIFEST_RELATIVE_PATH,
        current_dir / "manifest.json",
    ):
        if not manifest_path.is_file():
            continue
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"无法读取已安装 manifest: {manifest_path} ({exc})")
    return None


def _load_incremental_metadata(temp_dir: Path) -> dict | None:
    """如果当前 zip 是增量包，则加载增量包元数据。"""
    metadata_path = temp_dir / INCREMENTAL_METADATA_RELATIVE_PATH
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("package_type") != "incremental":
            logger.error("incremental_update.json 的 package_type 不是 incremental")
            return None
        if metadata.get("schema_version") != 2:
            logger.error("incremental_update.json 的 schema_version 必须为 2")
            return None
        if "from_version" not in metadata or "to_version" not in metadata:
            logger.error("incremental_update.json 缺少 from_version 或 to_version")
            return None
        if (
            "base_manifest_sha256" not in metadata
            or "target_manifest_sha256" not in metadata
        ):
            logger.error("incremental_update.json 缺少清单 sha256 绑定字段")
            return None
        if "files" not in metadata or "remove" not in metadata:
            logger.error("incremental_update.json 缺少 files 或 remove")
            return None
        logger.info(
            f"加载增量包元数据: {metadata['from_version']} -> {metadata['to_version']}, "
            f"files={len(metadata['files'])}, remove={len(metadata['remove'])}"
        )
        return metadata
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"加载 incremental_update.json 失败: {exc}")
        return None


def _load_mirror_chyan_changes(temp_dir: Path) -> dict | None:
    """读取 Mirror 酱增量包的 changes.json 差异描述。"""
    changes_path = temp_dir / MIRROR_CHYAN_CHANGES_RELATIVE_PATH
    if not changes_path.is_file():
        return None
    try:
        changes = json.loads(changes_path.read_text(encoding="utf-8"))
        if not isinstance(changes, dict):
            logger.error("changes.json 必须是 JSON 对象")
            return None
        for key in ("added", "modified", "deleted", "added_dir", "deleted_dir"):
            value = changes.get(key, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                logger.error(f"changes.json 的 {key} 字段必须是字符串数组")
                return None
        logger.info(
            "加载 Mirror 酱增量差异: "
            f"added={len(changes.get('added', []))}, "
            f"modified={len(changes.get('modified', []))}, "
            f"deleted={len(changes.get('deleted', []))}"
        )
        return changes
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"加载 changes.json 失败: {exc}")
        return None


def _safe_rmtree(path: Path, allowed_parent: Path, label: str) -> bool:
    """仅在目录仍位于预期父目录内时递归删除它。"""
    import shutil

    if not path.exists():
        return True
    try:
        if path.is_symlink():
            logger.warning(f"跳过符号链接目录清理: {path}")
            return False
        resolved_parent = allowed_parent.resolve()
        resolved_path = path.resolve()
        if resolved_path == resolved_parent or not resolved_path.is_relative_to(
            resolved_parent
        ):
            logger.warning(f"跳过越界目录清理: {path} -> {resolved_path}")
            return False
        if not path.is_dir():
            return True
        # 删除前再次检查，降低检查后被替换成链接的竞态风险。
        if path.is_symlink():
            logger.warning(f"跳过符号链接目录清理: {path}")
            return False
        shutil.rmtree(path)
        logger.info(f"已清理{label}: {path}")
        return True
    except OSError as exc:
        logger.warning(f"清理{label}失败: {path} ({exc})")
        return False


def _safe_unlink(path: Path, label: str) -> bool:
    """删除指定文件；清理失败时只记录日志，不中断主流程。"""
    try:
        if path.is_file():
            path.unlink()
            logger.info(f"已清理{label}: {path}")
        return True
    except OSError as exc:
        logger.warning(f"清理{label}失败: {path} ({exc})")
        return False


def _schedule_remove_dir_after_exit(path: Path, label: str) -> None:
    """在当前进程返回后，让 Windows 后台重试删除目录。"""
    if os.name != "nt":
        logger.warning(f"当前平台不支持延迟清理{label}: {path}")
        return
    script = (
        f'for /l %i in (1,1,20) do (rmdir /s /q "{path}" 2>NUL '
        "&& exit /b 0 & ping 127.0.0.1 -n 2 >NUL)"
    )
    try:
        subprocess.Popen(
            ["cmd", "/C", script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"已安排延迟清理{label}: {path}")
    except OSError as exc:
        logger.warning(f"安排延迟清理{label}失败: {path} ({exc})")


def _schedule_remove_file_after_exit(path: Path, label: str) -> None:
    """在当前进程返回后，让 Windows 后台重试删除文件。"""
    if os.name != "nt":
        logger.warning(f"当前平台不支持延迟清理{label}: {path}")
        return
    script = (
        f'for /l %i in (1,1,20) do (del /f /q "{path}" 2>NUL '
        "&& exit /b 0 & ping 127.0.0.1 -n 2 >NUL)"
    )
    try:
        subprocess.Popen(
            ["cmd", "/C", script],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"已安排延迟清理{label}: {path}")
    except OSError as exc:
        logger.warning(f"安排延迟清理{label}失败: {path} ({exc})")


def _cleanup_failed_install_artifacts(
    *,
    temp_dir: Path | None,
    plan_path: Path | None,
    package_path: Path,
) -> None:
    """清理 Rust 更新器接管前失败路径产生的本次更新临时文件。"""
    if plan_path is not None and not _safe_unlink(plan_path, "本次计划文件"):
        _schedule_remove_file_after_exit(plan_path, "本次计划文件")
    if temp_dir is not None and temp_dir.exists():
        if not _safe_rmtree(temp_dir, temp_dir.parent, "本次更新临时目录"):
            _schedule_remove_dir_after_exit(temp_dir, "本次更新临时目录")
    if package_path.exists() and not _safe_unlink(package_path, "更新包"):
        _schedule_remove_file_after_exit(package_path, "更新包")
    if package_path.parent.exists():
        try:
            package_path.parent.rmdir()
        except OSError:
            pass


def _build_status_file_paths(
    current_dir: Path,
    old_version: str,
    new_version: str,
) -> tuple[Path, Path]:
    """生成 logs/{旧版本}_{新版本}_updater_success|failure.txt 状态文件路径。"""
    prefix = f"{_safe_status_version(old_version)}_{_safe_status_version(new_version)}"
    logs_dir = current_dir / STATUS_DIR_NAME
    return (
        logs_dir / f"{prefix}_updater_success.txt",
        logs_dir / f"{prefix}_updater_failure.txt",
    )


def _cleanup_legacy_install_temp_dir(current_dir: Path) -> None:
    """清理旧方案遗留在安装根目录下的 _update_temp 目录。"""
    legacy_temp_dir = current_dir / "_update_temp"
    _safe_rmtree(legacy_temp_dir, current_dir, "旧临时目录")


def _cleanup_stale_update_temp_dirs(
    now: float | None = None,
    stale_seconds: int = STALE_UPDATE_TEMP_SECONDS,
) -> None:
    """尽力清理系统临时目录中已过期的更新解压目录。"""
    parent = Path(tempfile.gettempdir()) / UPDATE_TEMP_PARENT_NAME
    if parent.is_symlink() or not parent.is_dir():
        return

    current_time = time.time() if now is None else now
    for path in parent.iterdir():
        if not path.name.startswith(UPDATE_TEMP_PREFIX):
            continue
        if path.is_symlink() or not path.is_dir():
            continue
        try:
            age = current_time - path.stat().st_mtime
        except OSError:
            continue
        if age < stale_seconds:
            continue
        _safe_rmtree(path, parent, "过期更新临时目录")


def _build_update_temp_dir(current_dir: Path) -> Path:
    """为本次安装生成唯一的外部更新解压目录。"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    random_suffix = secrets.token_hex(8)
    return (
        Path(tempfile.gettempdir())
        / UPDATE_TEMP_PARENT_NAME
        / f"{UPDATE_TEMP_PREFIX}{timestamp}-{subprocess.os.getpid()}-{random_suffix}"
    )


def _protect_installed_updater_when_package_lacks_it(
    temp_dir: Path,
    remove_list: list[str],
    protected_list: list[str],
) -> tuple[list[str], list[str]]:
    """当更新包缺少 updater 时，保留安装目录中已有的 updater。"""
    if (temp_dir / UPDATER_RELATIVE_PATH).is_file():
        return remove_list, protected_list

    remove_list = [path for path in remove_list if path != UPDATER_RELATIVE_PATH]
    if UPDATER_RELATIVE_PATH not in protected_list:
        protected_list = [*protected_list, UPDATER_RELATIVE_PATH]
    return remove_list, sorted(protected_list)


def _is_protected(file_path: str, protected: set[str]) -> bool:
    """判断文件是否被 protected 列表保护（精确匹配或前缀目录匹配）。"""
    if file_path in protected:
        return True
    return any(p.endswith("/") and file_path.startswith(p) for p in protected)


def _compute_delete_list(
    current_dir: Path,
    new_manifest: dict,
) -> list[str]:
    """基于旧 manifest 计算需要删除的文件列表。

    删除旧 manifest 中的所有文件（排除 protected），
    确保所有程序文件都会被新版本替换。

    如果没有旧 manifest（首次升级到 manifest 方案），则扫描磁盘上
    安装目录中的文件，删除那些"大概率是旧程序"的文件（.exe, .dll,
    .pyd, .pyz 等），但跳过 manifest 识别的新版本文件和 protected 文件。

    Args:
        current_dir: 当前程序所在目录。
        new_manifest: 新版本的 manifest 字典。

    Returns:
        需要删除的文件相对路径列表（正斜杠格式）。
    """
    protected = set(new_manifest["protected"])
    new_files = set(new_manifest["files"])

    # 读取旧 manifest
    old_manifest_path = current_dir / MANIFEST_RELATIVE_PATH
    # 兼容旧版：旧版 manifest.json 在根目录
    if not old_manifest_path.is_file():
        old_manifest_path = current_dir / "manifest.json"

    old_files: set[str] = set()
    if old_manifest_path.is_file():
        try:
            old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
            old_files = set(old_manifest.get("files", []))
            logger.info(f"读取旧 manifest: {len(old_files)} 个文件")
        except Exception as exc:
            logger.warning(f"无法读取旧 manifest: {exc}")

    to_delete: list[str] = []

    if old_files:
        # 有旧 manifest：精确删除旧文件（排除 protected）
        for file in old_files:
            if not _is_protected(file, protected):
                to_delete.append(file)
    else:
        # 无旧 manifest（首次升级到 manifest 方案）：
        # 核心原则：不要删除用户本来就有的文件。
        # 此前版本的更新策略是"删文件夹+重新解压"，不需要额外兜底。
        # 只清理 manifest 中声明的目录内的旧程序文件残留（.exe/.dll/.pyd），
        # 确保 _internal 等目录干净即可，其他文件一律不动。
        _PROGRAM_EXTENSIONS = {".exe", ".dll", ".pyd", ".pyz", ".pyi"}

        # 从新 manifest 中提取涉及的目录前缀
        manifest_dirs: set[str] = set()
        for f in new_files:
            parts = f.split("/")
            for i in range(1, len(parts)):
                manifest_dirs.add("/".join(parts[:i]) + "/")

        for path in current_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = str(path.relative_to(current_dir).as_posix())
            except ValueError:
                continue
            # 跳过 protected
            if _is_protected(rel, protected):
                continue
            # 跳过新 manifest 中的文件
            if rel in new_files:
                continue
            # 只清理 manifest 涉及目录下的旧程序文件（.exe/.dll/.pyd 等）
            in_manifest_dir = any(rel.startswith(d) for d in manifest_dirs)
            if in_manifest_dir and path.suffix.lower() in _PROGRAM_EXTENSIONS:
                to_delete.append(rel)
        logger.info(
            f"首次升级（无旧 manifest）：清理 manifest 目录下的旧程序文件残留，"
            f"共 {len(to_delete)} 个"
        )

    logger.info(f"生成删除清单: {len(to_delete)} 个文件")
    return sorted(to_delete)


def _compute_copy_list(manifest: dict) -> list[str]:
    """计算需要复制的文件列表（已排除 protected 和 .git 相关文件）。

    Args:
        manifest: manifest 字典。

    Returns:
        需要复制的文件相对路径列表（正斜杠格式）。
    """
    protected = set(manifest["protected"])
    copy_files = [
        f
        for f in manifest["files"]
        if not _is_protected(f, protected)
        and not f.startswith(".git")
        and "/.git" not in f
        and not f.startswith("resources/.git")
        and "/resources/.git" not in f
    ]
    return sorted(copy_files)


def _compute_incremental_delete_list(metadata: dict, manifest: dict) -> list[str]:
    """返回增量包元数据中显式声明的删除清单。"""
    protected = set(manifest["protected"])
    return sorted(
        {
            file_path
            for file_path in metadata.get("remove", [])
            if isinstance(file_path, str) and not _is_protected(file_path, protected)
        }
    )


def _compute_incremental_copy_list(metadata: dict, manifest: dict) -> list[str] | None:
    """根据增量包元数据生成复制清单。

    增量包只携带元数据声明的文件；这些文件必须属于目标 manifest。
    元数据文件本身仅用于安装前校验，不会复制到安装目录。
    """
    protected = set(manifest["protected"])
    manifest_files = set(manifest["files"])
    copy_files: set[str] = set()

    for raw_file in metadata.get("files", []):
        if not isinstance(raw_file, str):
            logger.error("增量包 files 中存在非字符串条目")
            return None
        if raw_file == INCREMENTAL_METADATA_RELATIVE_PATH:
            continue
        if raw_file not in manifest_files:
            logger.error(f"增量包声明了不在目标 manifest 中的文件: {raw_file}")
            return None
        if _is_protected(raw_file, protected):
            continue
        copy_files.add(raw_file)

    copy_files.add(MANIFEST_RELATIVE_PATH)
    return sorted(copy_files)


def _build_mirror_chyan_protected_manifest(
    current_dir: Path,
    package_manifest: dict | None,
) -> dict:
    """为 Mirror 酱增量包选择 protected 来源，优先使用包内新清单。"""
    if package_manifest is not None and isinstance(
        package_manifest.get("protected"), list
    ):
        return package_manifest

    installed_manifest = _load_installed_manifest(current_dir)
    if installed_manifest is not None and isinstance(
        installed_manifest.get("protected"),
        list,
    ):
        return installed_manifest

    return {"files": [], "protected": sorted(ALLOWED_PROTECTED_PATHS)}


def _compute_mirror_chyan_delete_list(changes: dict, protected: list[str]) -> list[str]:
    """根据 Mirror 酱 changes.json 生成删除清单。"""
    protected_set = set(protected)
    delete_candidates = [
        *changes.get("deleted", []),
        *changes.get("deleted_dir", []),
    ]
    return sorted(
        {
            file_path
            for file_path in delete_candidates
            if isinstance(file_path, str)
            and not _is_protected(file_path, protected_set)
        }
    )


def _files_under_dirs(temp_dir: Path, dirs: list[str]) -> set[str]:
    """展开 Mirror 酱 added_dir 中声明的目录，收集其中的文件。"""
    temp_dir = temp_dir.resolve()
    files: set[str] = set()
    for raw_dir in dirs:
        if not isinstance(raw_dir, str):
            continue
        normalized = raw_dir.replace("\\", "/").strip("/")
        if not normalized:
            continue

        base = temp_dir / normalized
        try:
            base.resolve().relative_to(temp_dir)
        except ValueError:
            logger.warning(f"跳过越界 added_dir: {raw_dir}")
            continue

        if not base.is_dir():
            continue

        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                files.add(str(path.relative_to(temp_dir).as_posix()))
            except ValueError:
                logger.warning(f"跳过越界文件: {path}")
    return files


def _compute_mirror_chyan_copy_list(
    temp_dir: Path,
    changes: dict,
    protected: list[str],
) -> list[str]:
    """根据 Mirror 酱 changes.json 和解压内容生成复制清单。"""
    protected_set = set(protected)
    changed_files = {
        file_path
        for key in ("added", "modified")
        for file_path in changes.get(key, [])
        if isinstance(file_path, str)
    }
    changed_files.update(_files_under_dirs(temp_dir, changes.get("added_dir", [])))
    if not changed_files:
        changed_files = {
            str(path.relative_to(temp_dir).as_posix())
            for path in temp_dir.rglob("*")
            if path.is_file()
        }

    ignored_files = {
        MIRROR_CHYAN_CHANGES_RELATIVE_PATH,
        INCREMENTAL_METADATA_RELATIVE_PATH,
        "_plan.json",
    }
    return sorted(
        {
            file_path
            for file_path in changed_files
            if file_path not in ignored_files
            and (temp_dir / file_path).is_file()
            and not _is_protected(file_path, protected_set)
        }
    )


def _validate_incremental_package(
    current_dir: Path,
    manifest: dict,
    metadata: dict,
) -> bool:
    """校验增量包是否能应用到当前已安装版本。"""
    installed_manifest = _load_installed_manifest(current_dir)
    if installed_manifest is None:
        logger.error("当前安装目录没有 manifest，不能应用增量包")
        return False

    installed_version = str(installed_manifest.get("version", ""))
    expected_from = str(metadata.get("from_version", ""))
    if installed_version != expected_from:
        logger.error(
            f"增量包基线版本不匹配: 当前 {installed_version}, 需要 {expected_from}"
        )
        return False

    expected_base_sha256 = metadata.get("base_manifest_sha256")
    actual_base_sha256 = _compute_manifest_sha256(installed_manifest)
    if (
        not isinstance(expected_base_sha256, str)
        or actual_base_sha256 != expected_base_sha256
    ):
        logger.error(
            f"增量包基线清单 sha256 不匹配: 当前={actual_base_sha256}, "
            f"期望={expected_base_sha256}"
        )
        return False

    to_version = str(metadata.get("to_version", ""))
    manifest_version = str(manifest.get("version", ""))
    if manifest_version != to_version:
        logger.error(
            f"增量包目标版本与 manifest 不一致: metadata={to_version}, "
            f"manifest={manifest_version}"
        )
        return False

    expected_target_sha256 = metadata.get("target_manifest_sha256")
    actual_target_sha256 = _compute_manifest_sha256(manifest)
    if (
        not isinstance(expected_target_sha256, str)
        or actual_target_sha256 != expected_target_sha256
    ):
        logger.error(
            f"增量包目标清单 sha256 不匹配: 包内={actual_target_sha256}, "
            f"期望={expected_target_sha256}"
        )
        return False

    return True


def _compute_protected_list(manifest: dict) -> list[str]:
    """计算 updater 允许信任的 protected 路径列表。

    Args:
        manifest: manifest 字典。

    Returns:
        protected 相对路径列表（正斜杠格式）。
    """
    protected: set[str] = set()
    for raw_path in manifest["protected"]:
        if not isinstance(raw_path, str):
            logger.warning(f"忽略非字符串 protected 条目: {raw_path!r}")
            continue
        normalized = raw_path.replace("\\", "/")
        if normalized in ALLOWED_PROTECTED_PATHS:
            protected.add(normalized)
        else:
            logger.warning(f"忽略未在白名单内的 protected 条目: {normalized}")
    return sorted(protected)


def _generate_plan_json(
    temp_dir: Path,
    package_type: str,
    remove_list: list[str],
    copy_list: list[str],
    protected_list: list[str],
    copy_hashes: dict[str, str] | None = None,
) -> Path:
    """生成更新计划 JSON 文件。

    Args:
        temp_dir: 临时目录路径。
        package_type: 包类型（"manifest" 或 "fallback"）。
        remove_list: 需要删除的文件列表。
        copy_list: 需要复制的文件列表。
        protected_list: 受保护的文件列表。
        copy_hashes: 复制文件的 SHA-256 映射，旧包兼容时可为空。

    Returns:
        plan JSON 文件路径。
    """
    plan = {
        "package_type": package_type,
        "remove_list": remove_list,
        "copy_list": copy_list,
        "copy_hashes": copy_hashes or {},
        "protected_list": protected_list,
    }
    plan_path = temp_dir / "_plan.json"
    tmp_path = temp_dir / f"._plan.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    tmp_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, plan_path)
    logger.info(
        f"生成 plan JSON: remove={len(remove_list)}, "
        f"copy={len(copy_list)}, protected={len(protected_list)}"
    )
    return plan_path


def _compute_fallback_remove_list(current_dir: Path) -> list[str]:
    """无 manifest 时的回退删除列表。

    硬编码删除已知的程序目录和文件，与旧版 bat 脚本行为一致。

    Args:
        current_dir: 当前程序所在目录。

    Returns:
        需要删除的文件/目录相对路径列表。
    """
    to_delete = []
    known_items = [
        "endfield-essence-recognizer.exe",
        "_internal/",
        "resources/",
        "README.md",
        "界面白屏解决方法.md",
        "遇到报错解决方法.webp",
    ]
    for item in known_items:
        full_path = current_dir / item
        if full_path.exists():
            to_delete.append(item)
    return to_delete


def install_update(zip_path: Path) -> bool:
    """安装更新。

    流程：
    1. 解压更新包到临时目录（含路径穿越校验）
    2. 读取 manifest.json（``_internal/manifest.json`` 或根目录回退）
    3. 生成删除清单（有旧 manifest 则精确删除，无则保守清理旧程序文件）
    4. 生成复制清单（已排除 protected）
    5. 生成 protected 备份清单
    6. 生成 plan JSON 文件
    7. 启动 _internal/eer_updater.exe 并退出当前程序

    Args:
        zip_path: 更新包路径。

    Returns:
        bool: 安装是否成功。
    """
    import zipfile

    zip_path = Path(zip_path)
    temp_dir: Path | None = None
    plan_path: Path | None = None
    updater_started = False
    try:
        # 获取当前程序目录
        if getattr(sys, "frozen", False):
            current_dir = Path(sys.executable).parent
        else:
            current_dir = Path.cwd()

        # 创建临时解压目录。解压目录放在系统临时目录，避免安装目录残留 _update_temp。
        _cleanup_legacy_install_temp_dir(current_dir)
        _cleanup_stale_update_temp_dirs()
        temp_dir = _build_update_temp_dir(current_dir)
        if temp_dir.exists():
            _safe_rmtree(temp_dir, temp_dir.parent, "本次更新临时目录")
        temp_dir.mkdir(parents=True)

        # 解压更新包
        logger.info(f"解压更新包到: {temp_dir}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # 安全校验：使用 Path.relative_to() 拒绝路径穿越
            for member in zip_ref.namelist():
                if _is_path_traversal(temp_dir, member):
                    logger.error(f"拒绝可疑的 zip 条目（路径穿越）: {member}")
                    return False
            zip_ref.extractall(temp_dir)

        old_version = _load_installed_manifest_version(current_dir)

        # 尝试加载 manifest
        manifest = _load_manifest(temp_dir)
        mirror_chyan_changes = _load_mirror_chyan_changes(temp_dir)
        if (
            mirror_chyan_changes is None
            and (temp_dir / MIRROR_CHYAN_CHANGES_RELATIVE_PATH).is_file()
        ):
            return False

        if mirror_chyan_changes is not None:
            logger.info("使用 Mirror 酱增量包模式进行更新")
            protected_manifest = _build_mirror_chyan_protected_manifest(
                current_dir,
                manifest,
            )
            protected_list = _compute_protected_list(protected_manifest)
            remove_list = _compute_mirror_chyan_delete_list(
                mirror_chyan_changes,
                protected_list,
            )
            copy_list = _compute_mirror_chyan_copy_list(
                temp_dir,
                mirror_chyan_changes,
                protected_list,
            )
            package_type = "mirror_chyan_incremental"
            new_version = _safe_status_version(
                manifest.get("version") if manifest is not None else "unknown"
            )
            copy_hashes = _compute_copy_hashes(temp_dir, copy_list, manifest)
            plan_path = _generate_plan_json(
                temp_dir,
                package_type,
                remove_list,
                copy_list,
                protected_list,
                copy_hashes,
            )
        elif manifest is not None:
            incremental_metadata = _load_incremental_metadata(temp_dir)
            if (
                incremental_metadata is None
                and (temp_dir / INCREMENTAL_METADATA_RELATIVE_PATH).is_file()
            ):
                return False
            protected_list = _compute_protected_list(manifest)

            if incremental_metadata is not None:
                if not _validate_incremental_package(
                    current_dir,
                    manifest,
                    incremental_metadata,
                ):
                    return False

                logger.info("使用增量包模式进行更新")
                # 增量包不含未变化文件，只按 metadata 声明生成最小复制/删除清单。
                remove_list = _compute_incremental_delete_list(
                    incremental_metadata,
                    manifest,
                )
                copy_list = _compute_incremental_copy_list(
                    incremental_metadata,
                    manifest,
                )
                if copy_list is None:
                    return False
                package_type = "incremental"
            else:
                # 清单模式：精确删除，并在复制时排除受保护路径
                logger.info("使用 manifest 模式进行更新")
                remove_list = _compute_delete_list(current_dir, manifest)
                copy_list = _compute_copy_list(manifest)
                remove_list, protected_list = (
                    _protect_installed_updater_when_package_lacks_it(
                        temp_dir,
                        remove_list,
                        protected_list,
                    )
                )
                package_type = "manifest"

            new_version = _safe_status_version(manifest.get("version"))
            copy_hashes = _compute_copy_hashes(temp_dir, copy_list, manifest)
            plan_path = _generate_plan_json(
                temp_dir,
                package_type,
                remove_list,
                copy_list,
                protected_list,
                copy_hashes,
            )
        else:
            # 回退模式：兼容无 manifest 的旧版更新包
            logger.info("使用回退模式进行全量更新")
            remove_list = _compute_fallback_remove_list(current_dir)
            # 回退模式下，复制 temp_dir 中的所有文件
            copy_list = [
                str(p.relative_to(temp_dir).as_posix())
                for p in temp_dir.rglob("*")
                if p.is_file() and p.name != "_plan.json"
            ]
            protected_list = ["config.json", ".env"]
            new_version = "unknown"
            copy_hashes = _compute_copy_hashes(temp_dir, copy_list)
            plan_path = _generate_plan_json(
                temp_dir,
                "fallback",
                remove_list,
                copy_list,
                protected_list,
                copy_hashes,
            )

        # 独立更新器固定放在 _internal，避免用户在安装根目录误启动。
        packaged_updater = temp_dir / UPDATER_RELATIVE_PATH
        installed_updater = current_dir / UPDATER_RELATIVE_PATH
        updater_exe = (
            packaged_updater if packaged_updater.is_file() else installed_updater
        )
        if not updater_exe.is_file():
            logger.error(f"未找到更新器: {updater_exe}")
            return False

        # 构造命令行参数
        main_exe = current_dir / "endfield-essence-recognizer.exe"
        success_file, failure_file = _build_status_file_paths(
            current_dir,
            old_version,
            new_version,
        )

        args = [
            str(updater_exe),
            str(subprocess.os.getpid()),  # ParentPid
            str(current_dir),  # RootDir
            str(temp_dir),  # ExtractDir
            str(zip_path),  # PackagePath
            str(success_file),  # SuccessStatusFile
            str(failure_file),  # FailureStatusFile
            str(main_exe),  # RelaunchExecutable
            str(plan_path),  # PlanFile
        ]

        logger.info(f"启动更新器: {updater_exe}")
        logger.info(f"参数: RootDir={current_dir}, PlanFile={plan_path}")

        subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        updater_started = True

        # 延迟退出，确保响应返回给前端
        def delayed_exit() -> None:
            """稍后强制退出当前进程，让独立 updater 接管文件替换。"""
            import os
            import time

            time.sleep(1)
            os._exit(0)

        threading.Thread(target=delayed_exit, daemon=True).start()

        return True

    except Exception as exc:
        logger.error(f"安装更新失败: {exc}")
        return False
    finally:
        if not updater_started:
            _cleanup_failed_install_artifacts(
                temp_dir=temp_dir,
                plan_path=plan_path,
                package_path=zip_path,
            )
