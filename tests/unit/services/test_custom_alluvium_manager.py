"""自定义能量淤积点持久化服务的测试。"""

import json
from pathlib import Path

import pytest

from endfield_essence_recognizer.schemas.custom_alluvium import CustomAlluvium
from endfield_essence_recognizer.services.custom_alluvium_manager import (
    CustomAlluviumManager,
    CustomAlluviumReadError,
)


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """临时数据文件路径（文件本身不预先创建）。"""
    return tmp_path / "custom_alluviums.json"


@pytest.fixture
def manager(data_file: Path) -> CustomAlluviumManager:
    """使用临时文件的管理器实例。"""
    return CustomAlluviumManager(data_file)


def _entry(name: str = "测试淤积点") -> CustomAlluvium:
    """构造一条内容完整的自定义淤积点。"""
    return CustomAlluvium(
        name=name,
        attribute_stats=["gat_passive_attr_agi", "gat_passive_attr_main"],
        secondary_stats=["gat_passive_attr_atk"],
        skill_stats=["gst_passive_force"],
    )


def test_list_all_missing_file_returns_empty(manager: CustomAlluviumManager):
    """数据文件不存在时返回空列表，且不会凭空创建文件。"""
    assert manager.list_all() == []


def test_upsert_assigns_id_and_persists(
    manager: CustomAlluviumManager, data_file: Path
):
    """新建条目由后端分配稳定 ID 并落盘。"""
    saved = manager.upsert(_entry())

    assert len(saved) == 1
    assert saved[0].id
    assert saved[0].name == "测试淤积点"

    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk[0]["id"] == saved[0].id
    assert on_disk[0]["secondary_stats"] == ["gat_passive_attr_atk"]


def test_upsert_with_same_id_updates_in_place(manager: CustomAlluviumManager):
    """带既有 ID 的保存是覆盖，不会新增重复条目，顺序也保持不变。"""
    first, second = manager.upsert(_entry("甲")), manager.upsert(_entry("乙"))
    target_id = first[0].id

    saved = manager.upsert(
        CustomAlluvium(id=target_id, name="甲改名", skill_stats=["gst_passive_heal"])
    )

    assert [item.id for item in saved] == [target_id, second[1].id]
    assert saved[0].name == "甲改名"
    assert saved[0].skill_stats == ["gst_passive_heal"]


def test_upsert_strips_name_and_rejects_blank(manager: CustomAlluviumManager):
    """名称两端空白会被裁剪，纯空白视为非法输入。"""
    assert manager.upsert(_entry("  带空格  "))[0].name == "带空格"

    with pytest.raises(ValueError):
        manager.upsert(_entry("   "))


def test_upsert_creates_parent_dir(tmp_path: Path):
    """父目录不存在时自动创建（首次使用、目录被清理后都能写入）。"""
    data_file = tmp_path / "nested" / "custom_alluviums.json"
    manager = CustomAlluviumManager(data_file)

    assert len(manager.upsert(_entry())) == 1
    assert data_file.is_file()


def test_delete_removes_entry(manager: CustomAlluviumManager):
    """按稳定 ID 删除，其余条目保留。"""
    saved = manager.upsert(_entry("甲"))
    saved = manager.upsert(_entry("乙"))

    remaining = manager.delete(saved[0].id)

    assert [item.name for item in remaining] == ["乙"]
    assert [item.name for item in manager.list_all()] == ["乙"]


def test_delete_unknown_id_is_noop(manager: CustomAlluviumManager, data_file: Path):
    """删除不存在的 ID 不报错、不写盘。"""
    manager.upsert(_entry())
    before = data_file.read_text(encoding="utf-8")

    remaining = manager.delete("不存在的ID")

    assert len(remaining) == 1
    assert data_file.read_text(encoding="utf-8") == before


def test_list_all_backfills_missing_ids_and_keeps_them_stable(
    manager: CustomAlluviumManager, data_file: Path
):
    """手工编辑的条目缺少 ID 时补齐并写回，保证后续按 ID 删改能对上。"""
    data_file.write_text(
        json.dumps([{"name": "手改条目"}], ensure_ascii=False), encoding="utf-8"
    )

    first_read = manager.list_all()
    second_read = manager.list_all()

    assert first_read[0].id
    # 补好的 ID 已落盘，重复读取得到同一个 ID
    assert second_read[0].id == first_read[0].id
    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk[0]["id"] == first_read[0].id


def test_list_all_dedupes_duplicate_ids(
    manager: CustomAlluviumManager, data_file: Path
):
    """重复 ID 会在读取时拆开，否则删改会打到错误条目上。"""
    data_file.write_text(
        json.dumps(
            [{"id": "same", "name": "甲"}, {"id": "same", "name": "乙"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    entries = manager.list_all()

    assert len({item.id for item in entries}) == 2


def test_corrupt_file_is_backed_up_and_reported_as_empty(
    manager: CustomAlluviumManager, data_file: Path
):
    """文件损坏时备份原文件并返回空列表，不静默覆盖用户数据。"""
    data_file.write_text("{bad json", encoding="utf-8")

    assert manager.list_all() == []

    broken_files = list(data_file.parent.glob("custom_alluviums.json.broken*"))
    assert broken_files
    assert broken_files[0].read_text(encoding="utf-8") == "{bad json"
    assert not data_file.exists()


def test_invalid_utf8_is_treated_as_corrupt_file(
    manager: CustomAlluviumManager, data_file: Path
):
    """非法 UTF-8 也算内容损坏：备份后返回空列表，而不是让整个接口 500。"""
    broken_bytes = b'[{"name": "\xff\xfe"}]'
    data_file.write_bytes(broken_bytes)

    assert manager.list_all() == []

    broken_files = list(data_file.parent.glob("custom_alluviums.json.broken*"))
    assert broken_files
    assert broken_files[0].read_bytes() == broken_bytes


def test_read_error_is_not_treated_as_corrupt_file(
    manager: CustomAlluviumManager,
    data_file: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """读取失败（占用、权限）时不备份、不返回空列表，也不覆盖原文件。

    文件内容本身是好的，把读取失败当成「内容损坏」会把它改名备份，随后的
    保存再写入一份新列表，用户的条目就这样丢了。
    """
    original = json.dumps([{"id": "keep", "name": "甲"}], ensure_ascii=False)
    data_file.write_text(original, encoding="utf-8")

    def _deny_read(self: Path, **_kwargs: object) -> str:
        raise PermissionError("文件被占用")

    with monkeypatch.context() as patched:
        patched.setattr(Path, "read_text", _deny_read)

        with pytest.raises(CustomAlluviumReadError):
            manager.list_all()
        with pytest.raises(CustomAlluviumReadError):
            manager.upsert(_entry("乙"))

    assert data_file.read_text(encoding="utf-8") == original
    assert not list(data_file.parent.glob("custom_alluviums.json.broken*"))
