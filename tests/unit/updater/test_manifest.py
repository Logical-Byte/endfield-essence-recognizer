"""更新安装器和 manifest 生成的测试。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，以便导入 scripts 模块
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.generate_incremental_package import (  # noqa: E402
    INCREMENTAL_METADATA_RELATIVE_PATH,
    generate_incremental_package,
)
from scripts.generate_manifest import (  # noqa: E402
    MANIFEST_RELATIVE_PATH,
    PROTECTED_PATHS,
    generate_manifest,
    scan_dist_directory,
)


@pytest.fixture()
def fake_dist_dir(tmp_path: Path) -> Path:
    """创建一个模拟的 dist 目录结构。"""
    dist = tmp_path / "endfield-essence-recognizer"
    dist.mkdir()

    # 模拟典型 PyInstaller 输出
    (dist / "endfield-essence-recognizer.exe").write_text("exe")
    internal = dist / "_internal"
    internal.mkdir()
    (internal / "python3.dll").write_text("dll")
    (internal / "cv2").mkdir()
    (internal / "cv2" / "cv2.pyd").write_text("pyd")

    resources = dist / "resources"
    resources.mkdir()
    (resources / "images").mkdir()
    (resources / "images" / "error.webp").write_text("webp")

    (dist / "README.md").write_text("readme")
    (internal / "eer_updater.exe").write_text("updater")
    (dist / "config.json").write_text("{}")  # 用户配置，应该被 protected

    return dist


class TestScanDistDirectory:
    """扫描 dist 目录的测试。"""

    def test_scan_returns_all_files(self, fake_dist_dir: Path) -> None:
        """应返回目录中所有文件的相对路径。"""
        files = scan_dist_directory(fake_dist_dir)
        assert "endfield-essence-recognizer.exe" in files
        assert "_internal/python3.dll" in files
        assert "_internal/cv2/cv2.pyd" in files
        assert "resources/images/error.webp" in files
        assert "README.md" in files
        assert "_internal/eer_updater.exe" in files
        assert "config.json" in files

    def test_scan_uses_forward_slashes(self, fake_dist_dir: Path) -> None:
        """路径应统一使用正斜杠。"""
        files = scan_dist_directory(fake_dist_dir)
        for file_path in files:
            assert "\\" not in file_path, f"路径包含反斜杠: {file_path}"

    def test_scan_sorted_output(self, fake_dist_dir: Path) -> None:
        """输出应按字母顺序排序。"""
        files = scan_dist_directory(fake_dist_dir)
        assert files == sorted(files)

    def test_scan_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        """不存在的目录应抛出异常。"""
        with pytest.raises(FileNotFoundError):
            scan_dist_directory(tmp_path / "nonexistent")


class TestGenerateManifest:
    """生成 manifest 的测试。"""

    def test_manifest_structure(self, fake_dist_dir: Path) -> None:
        """manifest 应包含版本、文件、文件哈希和保护字段。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        assert "version" in manifest
        assert "files" in manifest
        assert "file_hashes" in manifest
        assert "protected" in manifest

    def test_manifest_version(self, fake_dist_dir: Path) -> None:
        """版本号应与传入参数一致。"""
        manifest = generate_manifest(fake_dist_dir, "2.3.4")
        assert manifest["version"] == "2.3.4"

    def test_manifest_files_count(self, fake_dist_dir: Path) -> None:
        """文件数量应匹配实际文件数 + manifest.json + _internal/eer_updater.exe 自身。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        # 7 个实际文件 + manifest.json 自身
        assert len(manifest["files"]) == 8

    def test_manifest_includes_self(self, fake_dist_dir: Path) -> None:
        """manifest.json 自身必须在 files 列表中。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        assert MANIFEST_RELATIVE_PATH in manifest["files"]

    def test_manifest_includes_updater(self, fake_dist_dir: Path) -> None:
        """dist 中的 _internal/eer_updater.exe 应进入 files 列表。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        assert "_internal/eer_updater.exe" in manifest["files"]

    def test_manifest_includes_file_hashes(self, fake_dist_dir: Path) -> None:
        """manifest 应记录实际文件的 SHA-256，manifest 自身除外。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        expected = hashlib.sha256(b"exe").hexdigest()

        assert manifest["file_hashes"]["endfield-essence-recognizer.exe"] == expected
        assert len(manifest["file_hashes"]["_internal/python3.dll"]) == 64
        assert MANIFEST_RELATIVE_PATH not in manifest["file_hashes"]

    def test_manifest_protected_defaults(self, fake_dist_dir: Path) -> None:
        """默认应使用 PROTECTED_PATHS 作为保护列表。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        assert manifest["protected"] == sorted(PROTECTED_PATHS)
        assert "config.json" in manifest["protected"]
        assert "logs/" in manifest["protected"]

    def test_manifest_custom_protected(self, fake_dist_dir: Path) -> None:
        """应支持自定义保护列表。"""
        custom = ["my_data.json", "custom_dir/"]
        manifest = generate_manifest(fake_dist_dir, "1.0.0", protected_paths=custom)
        assert manifest["protected"] == sorted(custom)

    def test_manifest_json_serializable(self, fake_dist_dir: Path) -> None:
        """manifest 应可序列化为 JSON。"""
        manifest = generate_manifest(fake_dist_dir, "1.0.0")
        text = json.dumps(manifest, ensure_ascii=False)
        restored = json.loads(text)
        assert restored == manifest


class TestProtectedPaths:
    """受保护路径的测试。"""

    def test_config_json_is_protected(self) -> None:
        """config.json 必须在保护列表中。"""
        assert "config.json" in PROTECTED_PATHS

    def test_profiles_json_is_protected(self) -> None:
        """profiles.json 必须在保护列表中，避免多账号配置被热更新覆盖。"""
        assert "profiles.json" in PROTECTED_PATHS

    def test_logs_dir_is_protected(self) -> None:
        """logs/ 目录必须在保护列表中。"""
        assert "logs/" in PROTECTED_PATHS

    def test_screenshots_dir_is_protected(self) -> None:
        """screenshots/ 目录必须在保护列表中。"""
        assert "screenshots/" in PROTECTED_PATHS

    def test_updater_exe_is_not_protected(self) -> None:
        """_internal/eer_updater.exe 需要参与复制，才能支持更新器替换。"""
        assert "_internal/eer_updater.exe" not in PROTECTED_PATHS


class TestDeleteListGeneration:
    """删除清单生成的测试。"""

    def test_delete_all_old_files_except_protected(self, tmp_path: Path) -> None:
        """应删除旧 manifest 中的所有文件（排除 protected）。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_delete_list,
        )

        # 创建旧 manifest
        current_dir = tmp_path / "current"
        current_dir.mkdir()
        old_manifest = {
            "version": "0.8.0",
            "files": ["app.exe", "old.dll", "lib.pyd", "config.json"],
            "protected": ["config.json", "logs/"],
        }
        (current_dir / "manifest.json").write_text(
            json.dumps(old_manifest), encoding="utf-8"
        )

        # 新 manifest
        new_manifest = {
            "version": "0.9.0",
            "files": ["app.exe", "new.dll", "lib.pyd"],
            "protected": ["config.json", "logs/"],
        }

        # 生成删除清单
        deleted_files = _compute_delete_list(current_dir, new_manifest)

        # 验证：应删除所有旧文件（排除 protected）
        assert "app.exe" in deleted_files
        assert "old.dll" in deleted_files
        assert "lib.pyd" in deleted_files
        assert "config.json" not in deleted_files  # protected

    def test_no_old_manifest_only_cleans_program_files_in_manifest_dirs(
        self, tmp_path: Path
    ) -> None:
        """首次升级（无旧 manifest）只清理 manifest 目录下的旧程序文件，不删用户文件。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_delete_list,
        )

        current_dir = tmp_path / "current"
        current_dir.mkdir()
        _internal = current_dir / "_internal"
        _internal.mkdir()
        # 旧程序文件在 manifest 目录下 → 应删除
        (_internal / "old.dll").write_text("old")
        (_internal / "old.exe").write_text("old")
        # 新文件 → 不删除（复制阶段覆盖）
        (_internal / "new.dll").write_text("new")
        # 根目录的用户文件 → 不删除
        (current_dir / "my_data.txt").write_text("user")
        (current_dir / "config.json").write_text("{}")  # protected
        # 根目录的旧程序文件（不在 manifest 目录下）→ 不删除
        (current_dir / "old_root.exe").write_text("old")
        # protected 目录
        (current_dir / "logs").mkdir()
        (current_dir / "logs" / "app.log").write_text("log")

        new_manifest = {
            "version": "0.9.0",
            "files": [
                "app.exe",
                "_internal/new.dll",
                "_internal/manifest.json",
                "config.json",
                "logs/app.log",
            ],
            "protected": ["config.json", "logs/"],
        }

        deleted_files = _compute_delete_list(current_dir, new_manifest)

        # _internal/ 下的旧程序文件 → 删除
        assert "_internal/old.dll" in deleted_files
        assert "_internal/old.exe" in deleted_files
        # _internal/ 下的新文件 → 不删除
        assert "_internal/new.dll" not in deleted_files
        # 根目录的用户文件 → 不删除
        assert "my_data.txt" not in deleted_files
        # 根目录的旧程序文件（不在 manifest 目录下）→ 不删除
        assert "old_root.exe" not in deleted_files
        # protected → 不删除
        assert "config.json" not in deleted_files
        assert "logs/app.log" not in deleted_files

    def test_no_old_manifest_empty_install_dir(self, tmp_path: Path) -> None:
        """首次升级且安装目录为空时，删除清单也应为空。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_delete_list,
        )

        current_dir = tmp_path / "current"
        current_dir.mkdir()
        # 安装目录为空

        new_manifest = {
            "version": "0.9.0",
            "files": ["app.exe", "new.dll"],
            "protected": ["config.json"],
        }

        deleted_files = _compute_delete_list(current_dir, new_manifest)
        assert deleted_files == []

    def test_protected_prefix_matching(self, tmp_path: Path) -> None:
        """protected 目录下的文件应被保护（前缀匹配）。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_delete_list,
        )

        current_dir = tmp_path / "current"
        current_dir.mkdir()
        old_manifest = {
            "version": "0.8.0",
            "files": ["app.exe", "logs/app.log", "logs/error.log"],
            "protected": ["logs/"],
        }
        (current_dir / "manifest.json").write_text(
            json.dumps(old_manifest), encoding="utf-8"
        )

        new_manifest = {
            "version": "0.9.0",
            "files": ["app.exe"],
            "protected": ["logs/"],
        }

        deleted_files = _compute_delete_list(current_dir, new_manifest)

        # logs/ 下的文件应被保护
        assert "app.exe" in deleted_files
        assert "logs/app.log" not in deleted_files
        assert "logs/error.log" not in deleted_files


class TestCopyListExcludesProtected:
    """复制清单应排除 protected 文件。"""

    def test_protected_excluded_from_copy_list(self) -> None:
        """protected 文件不应出现在复制清单中。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_copy_list,
        )

        manifest = {
            "version": "0.9.0",
            "files": ["app.exe", "config.json", "lib.dll", "logs/app.log"],
            "protected": ["config.json", "logs/"],
        }

        copy_files = _compute_copy_list(manifest)

        assert "app.exe" in copy_files
        assert "lib.dll" in copy_files
        assert "config.json" not in copy_files
        assert "logs/app.log" not in copy_files

    def test_manifest_json_always_in_copy_list(self) -> None:
        """manifest.json 自身（_internal/manifest.json）必须在复制清单中。"""
        from src.endfield_essence_recognizer.updater.installer import (
            MANIFEST_RELATIVE_PATH,
            _compute_copy_list,
        )

        manifest = {
            "version": "0.9.0",
            "files": ["app.exe", MANIFEST_RELATIVE_PATH],
            "protected": ["config.json"],
        }

        copy_files = _compute_copy_list(manifest)

        assert MANIFEST_RELATIVE_PATH in copy_files


class TestIncrementalPackage:
    """增量更新包生成与安装计划测试。"""

    def test_incremental_package_contains_only_changed_files(
        self, tmp_path: Path
    ) -> None:
        old_dist = tmp_path / "old"
        new_dist = tmp_path / "new"
        for dist in (old_dist, new_dist):
            (dist / "_internal").mkdir(parents=True)

        (old_dist / "app.exe").write_text("old")
        (old_dist / "same.dll").write_text("same")
        (old_dist / "removed.dll").write_text("removed")
        (old_dist / "_internal" / "eer_updater.exe").write_text("updater")
        old_manifest = generate_manifest(old_dist, "1.0.0")
        (old_dist / MANIFEST_RELATIVE_PATH).write_text(
            json.dumps(old_manifest), encoding="utf-8"
        )

        (new_dist / "app.exe").write_text("new")
        (new_dist / "same.dll").write_text("same")
        (new_dist / "added.dll").write_text("added")
        (new_dist / "_internal" / "eer_updater.exe").write_text("updater")
        new_manifest = generate_manifest(new_dist, "1.1.0")
        (new_dist / MANIFEST_RELATIVE_PATH).write_text(
            json.dumps(new_manifest), encoding="utf-8"
        )

        package_path = tmp_path / "delta.zip"
        metadata = generate_incremental_package(
            old_dist,
            new_dist,
            package_path,
            from_version="1.0.0",
            to_version="1.1.0",
        )

        assert package_path.is_file()
        assert "app.exe" in metadata["files"]
        assert "added.dll" in metadata["files"]
        assert "same.dll" not in metadata["files"]
        assert "removed.dll" in metadata["remove"]
        assert MANIFEST_RELATIVE_PATH in metadata["files"]
        assert metadata["schema_version"] == 2
        assert len(metadata["base_manifest_sha256"]) == 64
        assert len(metadata["target_manifest_sha256"]) == 64

        import zipfile

        with zipfile.ZipFile(package_path) as zf:
            names = set(zf.namelist())

        assert "app.exe" in names
        assert "added.dll" in names
        assert "same.dll" not in names
        assert INCREMENTAL_METADATA_RELATIVE_PATH in names

    def test_incremental_copy_list_uses_metadata_files(self) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_incremental_copy_list,
            _compute_incremental_delete_list,
        )

        manifest = {
            "version": "1.1.0",
            "files": ["app.exe", "same.dll", "added.dll", MANIFEST_RELATIVE_PATH],
            "protected": ["config.json", "logs/"],
        }
        metadata = {
            "files": ["app.exe", "added.dll", MANIFEST_RELATIVE_PATH],
            "remove": ["old.dll", "logs/app.log"],
        }

        assert _compute_incremental_copy_list(metadata, manifest) == [
            MANIFEST_RELATIVE_PATH,
            "added.dll",
            "app.exe",
        ]
        assert _compute_incremental_delete_list(metadata, manifest) == ["old.dll"]

    def test_mirror_chyan_changes_generates_copy_and_delete_lists(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            MIRROR_CHYAN_CHANGES_RELATIVE_PATH,
            _compute_mirror_chyan_copy_list,
            _compute_mirror_chyan_delete_list,
            _load_mirror_chyan_changes,
        )

        changes = {
            "added": ["app.exe"],
            "modified": ["_internal/manifest.json", "logs/app.log"],
            "deleted": ["old.dll", "config.json"],
            "deleted_dir": ["old_dir"],
        }
        (tmp_path / "_internal").mkdir()
        (tmp_path / "app.exe").write_text("new", encoding="utf-8")
        (tmp_path / "_internal" / "manifest.json").write_text("{}", encoding="utf-8")
        (tmp_path / MIRROR_CHYAN_CHANGES_RELATIVE_PATH).write_text(
            json.dumps(changes),
            encoding="utf-8",
        )

        loaded = _load_mirror_chyan_changes(tmp_path)

        assert loaded == changes
        assert _compute_mirror_chyan_copy_list(
            tmp_path,
            changes,
            ["config.json", "logs/"],
        ) == ["_internal/manifest.json", "app.exe"]
        assert _compute_mirror_chyan_delete_list(
            changes,
            ["config.json", "logs/"],
        ) == ["old.dll", "old_dir"]

    def test_mirror_chyan_added_dir_is_expanded(self, tmp_path: Path) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_mirror_chyan_copy_list,
        )

        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "root.txt").write_text("root", encoding="utf-8")
        (tmp_path / "assets" / "nested").mkdir()
        (tmp_path / "assets" / "nested" / "child.txt").write_text(
            "child",
            encoding="utf-8",
        )

        changes = {
            "added": [],
            "modified": [],
            "deleted": [],
            "added_dir": ["assets/"],
            "deleted_dir": [],
        }

        copy_list = _compute_mirror_chyan_copy_list(
            tmp_path,
            changes,
            ["config.json", "logs/"],
        )

        assert copy_list == [
            "assets/nested/child.txt",
            "assets/root.txt",
        ]

    def test_incremental_package_requires_matching_installed_version(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_manifest_sha256,
            _validate_incremental_package,
        )

        installed_manifest_path = tmp_path / MANIFEST_RELATIVE_PATH
        installed_manifest_path.parent.mkdir()
        installed_manifest = {"version": "1.0.0", "files": []}
        installed_manifest_path.write_text(
            json.dumps(installed_manifest), encoding="utf-8"
        )
        target_manifest = {"version": "1.1.0"}
        metadata = {
            "from_version": "1.0.0",
            "to_version": "1.1.0",
            "base_manifest_sha256": _compute_manifest_sha256(installed_manifest),
            "target_manifest_sha256": _compute_manifest_sha256(target_manifest),
        }

        assert _validate_incremental_package(tmp_path, target_manifest, metadata)
        assert not _validate_incremental_package(
            tmp_path,
            target_manifest,
            {**metadata, "from_version": "0.9.0"},
        )
        assert not _validate_incremental_package(
            tmp_path,
            target_manifest,
            {**metadata, "base_manifest_sha256": "0" * 64},
        )


class TestIncrementalPackageSelection:
    """增量包选择测试。"""

    def test_incremental_package_requires_explicit_target_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.endfield_essence_recognizer.updater import checker

        monkeypatch.setattr(checker, "__version__", "1.0.0")
        data = {
            "incrementalPackages": [
                {
                    "fromVersion": "1.0.0",
                    "downloadUrl": "https://example.invalid/missing-target.zip",
                },
                {
                    "fromVersion": "1.0.0",
                    "toVersion": "1.1.0",
                    "downloadUrl": "https://example.invalid/target.zip",
                },
            ]
        }

        package = checker._find_incremental_package(data, "1.1.0")

        assert package is not None
        assert package["downloadUrl"].endswith("target.zip")

    def test_incremental_package_accepts_v_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.endfield_essence_recognizer.updater import checker

        monkeypatch.setattr(checker, "__version__", "1.0.0")
        data = {
            "incrementalPackages": [
                {
                    "fromVersion": "v1.0.0",
                    "toVersion": "v1.1.0",
                    "downloadUrl": "https://example.invalid/target.zip",
                },
            ]
        }

        package = checker._find_incremental_package(data, "1.1.0")

        assert package is not None
        assert package["downloadUrl"].endswith("target.zip")


class TestProtectedBackupList:
    """protected 文件备份清单测试。"""

    def test_protected_files_list(self) -> None:
        """只信任白名单内的 protected 条目。"""
        from src.endfield_essence_recognizer.updater.installer import (
            UPDATER_RELATIVE_PATH,
            _compute_protected_list,
        )

        manifest = {
            "version": "0.9.0",
            "files": ["app.exe", "config.json"],
            "protected": [
                "config.json",
                "logs/",
                ".env",
                UPDATER_RELATIVE_PATH,
                "_internal/evil.dll",
            ],
        }

        entries = _compute_protected_list(manifest)

        # 允许的用户数据路径应进入 plan，目录前缀也由 Rust updater 二次保护。
        assert "config.json" in entries
        assert "logs/" in entries
        assert ".env" in entries
        # 程序文件不能被 manifest 注入 protected，避免阻止更新/删除。
        assert UPDATER_RELATIVE_PATH not in entries
        assert "_internal/evil.dll" not in entries


class TestStatusFilePaths:
    """更新状态文件路径测试。"""

    def test_status_files_are_written_under_logs_with_versions(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _build_status_file_paths,
        )

        success_file, failure_file = _build_status_file_paths(
            tmp_path,
            "0.8.0",
            "0.9.0",
        )

        assert success_file == tmp_path / "logs" / "0.8.0_0.9.0_updater_success.txt"
        assert failure_file == tmp_path / "logs" / "0.8.0_0.9.0_updater_failure.txt"

    def test_status_file_versions_are_sanitized(self, tmp_path: Path) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _build_status_file_paths,
        )

        success_file, _ = _build_status_file_paths(tmp_path, "0/8 beta", "0:9")

        assert success_file.name == "0_8_beta_0_9_updater_success.txt"

    def test_installed_manifest_version_is_read_from_internal_manifest(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            MANIFEST_RELATIVE_PATH,
            _load_installed_manifest_version,
        )

        manifest_path = tmp_path / MANIFEST_RELATIVE_PATH
        manifest_path.parent.mkdir()
        manifest_path.write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")

        assert _load_installed_manifest_version(tmp_path) == "1.2.3"


class TestUpdaterProtection:
    """更新包缺少 updater 时应保留当前安装的 updater。"""

    def test_installed_updater_is_protected_when_package_lacks_updater(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            UPDATER_RELATIVE_PATH,
            _protect_installed_updater_when_package_lacks_it,
        )

        remove_list, protected_list = _protect_installed_updater_when_package_lacks_it(
            tmp_path,
            [UPDATER_RELATIVE_PATH, "_internal/python3.dll"],
            ["config.json"],
        )

        assert UPDATER_RELATIVE_PATH not in remove_list
        assert "_internal/python3.dll" in remove_list
        assert UPDATER_RELATIVE_PATH in protected_list

    def test_packaged_updater_is_not_protected_when_package_contains_updater(
        self, tmp_path: Path
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            UPDATER_RELATIVE_PATH,
            _protect_installed_updater_when_package_lacks_it,
        )

        updater = tmp_path / UPDATER_RELATIVE_PATH
        updater.parent.mkdir()
        updater.write_text("updater")

        remove_list, protected_list = _protect_installed_updater_when_package_lacks_it(
            tmp_path,
            [UPDATER_RELATIVE_PATH],
            ["config.json"],
        )

        assert remove_list == [UPDATER_RELATIVE_PATH]
        assert protected_list == ["config.json"]


class TestUpdateTempDir:
    """更新解压临时目录测试。"""

    def test_update_temp_dir_is_unique_and_outside_install_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _build_update_temp_dir,
        )

        monkeypatch.setattr(
            "src.endfield_essence_recognizer.updater.installer.time.strftime",
            lambda _fmt: "20260510-143601",
        )
        monkeypatch.setattr(
            "src.endfield_essence_recognizer.updater.installer.subprocess.os.getpid",
            lambda: 12345,
        )

        temp_dir = _build_update_temp_dir(tmp_path)

        assert not temp_dir.is_relative_to(tmp_path)
        assert temp_dir.name.startswith("update-20260510-143601-12345-")
        assert len(temp_dir.name.rsplit("-", maxsplit=1)[-1]) == 16

    def test_plan_json_is_written_atomically(self, tmp_path: Path) -> None:
        """plan JSON 应通过临时文件原子替换写入。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _generate_plan_json,
        )

        plan_path = _generate_plan_json(
            tmp_path,
            "manifest",
            ["old.dll"],
            ["new.dll"],
            ["config.json"],
            {"new.dll": "a" * 64},
        )

        assert plan_path == tmp_path / "_plan.json"
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        assert data["remove_list"] == ["old.dll"]
        assert data["copy_hashes"] == {"new.dll": "a" * 64}
        assert not list(tmp_path.glob("._plan.*.tmp"))

    def test_copy_hashes_fallback_to_extracted_files(self, tmp_path: Path) -> None:
        """旧包缺少 manifest 哈希时，应使用解压目录中的实际文件哈希。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_copy_hashes,
        )

        (tmp_path / "new.dll").write_text("new", encoding="utf-8")

        assert _compute_copy_hashes(tmp_path, ["new.dll"]) == {
            "new.dll": hashlib.sha256(b"new").hexdigest()
        }

    def test_copy_hashes_prefer_manifest_hashes(self, tmp_path: Path) -> None:
        """新版 manifest 自带哈希时，应优先使用 manifest 声明值。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _compute_copy_hashes,
        )

        (tmp_path / "new.dll").write_text("new", encoding="utf-8")
        manifest = {"file_hashes": {"new.dll": "b" * 64}}

        assert _compute_copy_hashes(tmp_path, ["new.dll"], manifest) == {
            "new.dll": "b" * 64
        }

    def test_legacy_install_temp_dir_is_cleaned(self, tmp_path: Path) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            _cleanup_legacy_install_temp_dir,
        )

        legacy_temp = tmp_path / "_update_temp"
        legacy_temp.mkdir()
        (legacy_temp / "old.tmp").write_text("old")

        _cleanup_legacy_install_temp_dir(tmp_path)

        assert not legacy_temp.exists()

    def test_stale_external_update_temp_dirs_are_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.endfield_essence_recognizer.updater.installer import (
            UPDATE_TEMP_PARENT_NAME,
            _cleanup_stale_update_temp_dirs,
        )

        monkeypatch.setattr(
            "src.endfield_essence_recognizer.updater.installer.tempfile.gettempdir",
            lambda: str(tmp_path),
        )
        parent = tmp_path / UPDATE_TEMP_PARENT_NAME
        stale = parent / "update-20260509-010101-1"
        fresh = parent / "update-20260510-143601-2"
        unrelated = parent / "keep-this"
        stale.mkdir(parents=True)
        fresh.mkdir()
        unrelated.mkdir()
        (stale / "old.tmp").write_text("old")
        (fresh / "new.tmp").write_text("new")
        (unrelated / "keep.tmp").write_text("keep")
        old_time = 1000.0
        fresh_time = 2000.0
        import os

        os.utime(stale, (old_time, old_time))
        os.utime(fresh, (fresh_time, fresh_time))

        _cleanup_stale_update_temp_dirs(now=2000.0, stale_seconds=500)

        assert not stale.exists()
        assert fresh.exists()
        assert unrelated.exists()

    def test_stale_external_update_temp_symlink_is_not_followed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """清理过期临时目录时不应跟随符号链接删除外部目录。"""
        import os

        from src.endfield_essence_recognizer.updater.installer import (
            UPDATE_TEMP_PARENT_NAME,
            _cleanup_stale_update_temp_dirs,
        )

        monkeypatch.setattr(
            "src.endfield_essence_recognizer.updater.installer.tempfile.gettempdir",
            lambda: str(tmp_path),
        )
        parent = tmp_path / UPDATE_TEMP_PARENT_NAME
        parent.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        link = parent / "update-20260509-010101-link"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"当前环境无法创建符号链接: {exc}")

        _cleanup_stale_update_temp_dirs(now=2000.0, stale_seconds=0)

        assert (outside / "keep.txt").exists()


class TestPathTraversalProtection:
    """路径穿越保护测试。"""

    def test_normal_path_allowed(self, tmp_path: Path) -> None:
        """正常路径不应被拒绝。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _is_path_traversal,
        )

        assert not _is_path_traversal(tmp_path, "app.exe")
        assert not _is_path_traversal(tmp_path, "_internal/python3.dll")
        assert not _is_path_traversal(tmp_path, "resources/images/icon.png")

    def test_dotdot_traversal_rejected(self, tmp_path: Path) -> None:
        """../ 路径穿越应被拒绝。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _is_path_traversal,
        )

        assert _is_path_traversal(tmp_path, "../evil.exe")
        assert _is_path_traversal(tmp_path, "subdir/../../evil.exe")
        assert _is_path_traversal(tmp_path, "_internal/../../../etc/passwd")

    def test_prefix_collision_rejected(self, tmp_path: Path) -> None:
        """前缀碰撞绕过应被拒绝（字符串前缀法的已知弱点）。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _is_path_traversal,
        )

        # 使用类似前缀的目录名
        tricky_dir = tmp_path / "update"
        tricky_dir.mkdir()

        # "update_evil/../update/../../evil.exe" 不应通过
        assert _is_path_traversal(tricky_dir, "../update/../../evil.exe")

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        """绝对路径应被拒绝。"""
        from src.endfield_essence_recognizer.updater.installer import (
            _is_path_traversal,
        )

        # 在 Linux 上测试绝对路径
        assert _is_path_traversal(tmp_path, "/etc/passwd")
