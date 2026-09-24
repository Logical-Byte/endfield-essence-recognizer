"""生成文件级增量更新包。

增量包只包含旧版和新版 PyInstaller dist 目录之间新增或发生变化的文件，
同时额外写入目标版本的 ``_internal/manifest.json`` 和增量包元数据。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

try:
    from generate_manifest import (
        MANIFEST_RELATIVE_PATH,
        PROTECTED_PATHS,
        compute_file_sha256,
        generate_manifest,
        read_version_from_pyproject,
    )
except ModuleNotFoundError:  # pragma: no cover - 作为包导入时使用
    from scripts.generate_manifest import (
        MANIFEST_RELATIVE_PATH,
        PROTECTED_PATHS,
        compute_file_sha256,
        generate_manifest,
        read_version_from_pyproject,
    )

# 增量包元数据固定放在 _internal 下，避免污染安装根目录。
INCREMENTAL_METADATA_RELATIVE_PATH = "_internal/incremental_update.json"


def _compute_manifest_sha256(manifest: dict) -> str:
    """计算清单的稳定内容哈希，用于绑定增量包基线和目标。"""
    canonical = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_protected(file_path: str, protected: set[str]) -> bool:
    """判断文件是否命中 protected 规则，避免把用户数据打进增量包。"""
    if file_path in protected:
        return True
    return any(
        protected_path.endswith("/") and file_path.startswith(protected_path)
        for protected_path in protected
    )


def _load_or_create_manifest(
    dist_dir: Path,
    version: str,
    *,
    write: bool,
) -> dict:
    """读取 dist 中已有 manifest；必要时为新版 dist 补写 manifest。"""
    manifest_path = dist_dir / MANIFEST_RELATIVE_PATH
    if manifest_path.is_file():
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest = generate_manifest(dist_dir, version)
    if write:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return manifest


def _changed_or_new_files(
    old_dist_dir: Path,
    new_dist_dir: Path,
    old_manifest: dict,
    new_manifest: dict,
) -> list[str]:
    """计算增量包需要携带的新增或变更文件。"""
    old_files = set(old_manifest["files"])
    protected = set(new_manifest["protected"])
    changed: list[str] = []

    for file_path in sorted(new_manifest["files"]):
        if _is_protected(file_path, protected):
            continue
        if file_path == INCREMENTAL_METADATA_RELATIVE_PATH:
            continue

        new_path = new_dist_dir / file_path
        old_path = old_dist_dir / file_path
        if not new_path.is_file():
            raise FileNotFoundError(f"新版 dist 缺少 manifest 声明的文件: {file_path}")

        if file_path not in old_files or not old_path.is_file():
            changed.append(file_path)
            continue

        if compute_file_sha256(new_path) != compute_file_sha256(old_path):
            changed.append(file_path)

    if MANIFEST_RELATIVE_PATH not in changed:
        changed.append(MANIFEST_RELATIVE_PATH)
    return sorted(set(changed))


def _removed_files(old_manifest: dict, new_manifest: dict) -> list[str]:
    """计算新版中已删除、且不受 protected 保护的旧文件。"""
    protected = set(new_manifest["protected"])
    new_files = set(new_manifest["files"])
    removed = [
        file_path
        for file_path in old_manifest["files"]
        if file_path not in new_files and not _is_protected(file_path, protected)
    ]
    return sorted(set(removed))


def generate_incremental_package(
    old_dist_dir: Path,
    new_dist_dir: Path,
    output_path: Path,
    *,
    from_version: str,
    to_version: str,
    write_new_manifest: bool = True,
) -> dict:
    """创建增量更新 zip，并返回写入包内的元数据。"""
    old_dist_dir = old_dist_dir.resolve()
    new_dist_dir = new_dist_dir.resolve()
    output_path = output_path.resolve()

    old_manifest = _load_or_create_manifest(
        old_dist_dir,
        from_version,
        write=False,
    )
    new_manifest = _load_or_create_manifest(
        new_dist_dir,
        to_version,
        write=write_new_manifest,
    )

    if old_manifest.get("version") and old_manifest["version"] != from_version:
        raise ValueError(
            f"旧 manifest 版本 {old_manifest['version']} != {from_version}"
        )
    if new_manifest.get("version") and new_manifest["version"] != to_version:
        raise ValueError(f"新 manifest 版本 {new_manifest['version']} != {to_version}")

    files = _changed_or_new_files(
        old_dist_dir, new_dist_dir, old_manifest, new_manifest
    )
    removed = _removed_files(old_manifest, new_manifest)
    # 元数据由 Python 安装器读取；Rust updater 仍只消费转换后的 _plan.json。
    metadata = {
        "schema_version": 2,
        "format": 1,
        "package_type": "incremental",
        "from_version": from_version,
        "to_version": to_version,
        "base_manifest_sha256": _compute_manifest_sha256(old_manifest),
        "target_manifest_sha256": _compute_manifest_sha256(new_manifest),
        "target_manifest": MANIFEST_RELATIVE_PATH,
        "files": files,
        "remove": removed,
        "protected": sorted(new_manifest.get("protected", PROTECTED_PATHS)),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(new_dist_dir / file_path, file_path)
        zf.writestr(
            INCREMENTAL_METADATA_RELATIVE_PATH,
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        )

    return metadata


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="生成文件级增量更新包")
    parser.add_argument("--old-dist-dir", type=Path, required=True)
    parser.add_argument("--new-dist-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from-version", type=str, required=True)
    parser.add_argument("--to-version", type=str, default=None)
    parser.add_argument(
        "--no-write-new-manifest",
        action="store_true",
        help="如果新 dist 缺少 manifest，不自动写入",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.resolve()
    to_version = args.to_version or read_version_from_pyproject(project_root)
    metadata = generate_incremental_package(
        args.old_dist_dir,
        args.new_dist_dir,
        args.output,
        from_version=args.from_version,
        to_version=to_version,
        write_new_manifest=not args.no_write_new_manifest,
    )

    print(
        f"Incremental package generated: "
        f"{args.output} ({len(metadata['files'])} files, "
        f"{len(metadata['remove'])} removed)"
    )


if __name__ == "__main__":
    main()
