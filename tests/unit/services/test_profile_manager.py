"""账号管理器服务的测试。"""

import json
from pathlib import Path

import pytest

from endfield_essence_recognizer.schemas.profile import (
    TreasureMatrixEntry,
)
from endfield_essence_recognizer.services import (
    profile_manager as profile_manager_module,
)
from endfield_essence_recognizer.services.profile_manager import (
    ProfileLoadError,
    ProfileManager,
    ProfileSaveError,
)


@pytest.fixture
def temp_profiles_file(tmp_path: Path) -> Path:
    """创建临时账号配置文件路径。"""
    return tmp_path / "profiles.json"


@pytest.fixture
def profile_manager(temp_profiles_file: Path) -> ProfileManager:
    """创建使用临时文件的 ProfileManager 实例。"""
    return ProfileManager(temp_profiles_file)


def test_profile_manager_init(profile_manager: ProfileManager):
    """测试 ProfileManager 初始化。"""
    assert profile_manager is not None


def test_load_creates_default_profile(profile_manager: ProfileManager):
    """测试 load() 在文件不存在时创建默认账号。"""
    profile_manager.load()
    collection = profile_manager.get_collection()
    assert "default" in collection.profiles
    assert collection.active_profile == "default"


def test_load_corrupted_profiles_does_not_overwrite_existing_file(
    temp_profiles_file: Path,
):
    """损坏的账号配置不能被默认配置静默覆盖。"""
    temp_profiles_file.write_text("{bad json", encoding="utf-8")

    manager = ProfileManager(temp_profiles_file)

    with pytest.raises(ProfileLoadError):
        manager.load()

    broken_files = list(temp_profiles_file.parent.glob("profiles.json.broken*"))
    assert broken_files
    assert broken_files[0].read_text(encoding="utf-8") == "{bad json"
    assert not temp_profiles_file.exists()


def test_save_failure_does_not_update_in_memory_collection(
    profile_manager: ProfileManager, monkeypatch: pytest.MonkeyPatch
):
    """保存失败时不能让内存状态伪装成已经切换成功。"""
    profile_manager.load()

    def fake_save(*args, **kwargs):
        raise ProfileSaveError("disk full")

    monkeypatch.setattr(profile_manager_module, "_save_profiles_to_file", fake_save)

    with pytest.raises(ProfileSaveError):
        profile_manager.switch_profile("new_account")

    assert profile_manager.get_active_profile_name() == "default"
    assert "new_account" not in profile_manager.get_collection().profiles


def test_switch_profile_creates_new(profile_manager: ProfileManager):
    """测试切换到不存在的账号会创建它。"""
    profile_manager.load()
    profile = profile_manager.switch_profile("test_account")
    assert profile.name == "test_account"
    assert profile_manager.get_active_profile_name() == "test_account"


def test_validate_profile_name_empty():
    """测试空账号名称会被拒绝。"""
    with pytest.raises(ValueError, match="账号名称不能为空"):
        ProfileManager._validate_profile_name("")
    with pytest.raises(ValueError, match="账号名称不能为空"):
        ProfileManager._validate_profile_name("   ")


def test_validate_profile_name_too_long():
    """测试超过 32 个字符的账号名称会被拒绝。"""
    with pytest.raises(ValueError, match="账号名称不能超过 32 个字符"):
        ProfileManager._validate_profile_name("a" * 33)


def test_validate_profile_name_forbidden_chars():
    """测试包含禁止字符的账号名称会被拒绝。"""
    forbidden = ["/", "\\", "\x00", "\n", "\r", "\t"]
    for char in forbidden:
        with pytest.raises(ValueError, match="账号名称包含非法字符"):
            ProfileManager._validate_profile_name(f"test{char}name")


def test_rename_profile(profile_manager: ProfileManager):
    """测试重命名账号。"""
    profile_manager.load()
    profile_manager.switch_profile("old_name")
    profile = profile_manager.rename_profile("old_name", "new_name")
    assert profile.name == "new_name"
    assert "new_name" in profile_manager.get_collection().profiles
    assert "old_name" not in profile_manager.get_collection().profiles
    assert profile_manager.get_active_profile_name() == "new_name"


def test_rename_nonexistent_profile(profile_manager: ProfileManager):
    """测试重命名不存在的账号会抛出 ValueError。"""
    profile_manager.load()
    with pytest.raises(ValueError, match="不存在"):
        profile_manager.rename_profile("nonexistent", "new_name")


def test_rename_to_existing_name(profile_manager: ProfileManager):
    """测试重命名为已存在的名称会抛出 ValueError。"""
    profile_manager.load()
    profile_manager.switch_profile("profile1")
    profile_manager.switch_profile("profile2")
    with pytest.raises(ValueError, match="已存在"):
        profile_manager.rename_profile("profile1", "profile2")


def test_delete_profile(profile_manager: ProfileManager):
    """测试删除账号。"""
    profile_manager.load()
    profile_manager.switch_profile("to_delete")
    profile_manager.switch_profile("default")
    profile_manager.delete_profile("to_delete")
    assert "to_delete" not in profile_manager.get_collection().profiles


def test_delete_default_profile(profile_manager: ProfileManager):
    """测试删除默认账号是被禁止的。"""
    profile_manager.load()
    with pytest.raises(ValueError, match="不能删除默认账号"):
        profile_manager.delete_profile("default")


def test_delete_active_profile_falls_back_to_default(profile_manager: ProfileManager):
    """测试删除当前激活的账号后自动切换回默认账号。"""
    profile_manager.load()
    profile_manager.switch_profile("active")
    profile_manager.delete_profile("active")
    collection = profile_manager.get_collection()
    assert "active" not in collection.profiles
    assert collection.active_profile == "default"


def test_rename_default_profile(profile_manager: ProfileManager):
    """测试重命名默认账号，default_profile 与 active_profile 同步更新。"""
    profile_manager.load()
    profile = profile_manager.rename_profile("default", "我的账号")
    collection = profile_manager.get_collection()
    assert profile.name == "我的账号"
    assert "我的账号" in collection.profiles
    assert "default" not in collection.profiles
    assert collection.active_profile == "我的账号"
    assert collection.default_profile == "我的账号"


def test_delete_renamed_default_profile(profile_manager: ProfileManager):
    """测试删除改名后的默认账号仍被禁止。"""
    profile_manager.load()
    profile_manager.rename_profile("default", "我的账号")
    with pytest.raises(ValueError, match="不能删除默认账号"):
        profile_manager.delete_profile("我的账号")


def test_delete_active_profile_falls_back_to_renamed_default(
    profile_manager: ProfileManager,
):
    """删除激活账号后回退到改名后的默认账号，且默认账号数据可用。"""
    profile_manager.load()
    profile_manager.rename_profile("default", "我的账号")
    profile_manager.switch_profile("active")
    profile_manager.delete_profile("active")
    collection = profile_manager.get_collection()
    assert "active" not in collection.profiles
    assert collection.active_profile == "我的账号"
    # 回退后默认账号可正常读取，不会出现 KeyError 或幽灵空账号
    assert profile_manager.get_active_profile_name() == "我的账号"
    assert profile_manager.get_active_profile().name == "我的账号"


def test_rename_default_profile_keeps_other_active(profile_manager: ProfileManager):
    """重命名默认账号时，若激活的是其它账号则只更新 default_profile。"""
    profile_manager.load()
    profile_manager.switch_profile("alt")
    profile_manager.rename_profile("default", "我的账号")
    collection = profile_manager.get_collection()
    assert collection.default_profile == "我的账号"
    assert collection.active_profile == "alt"


def test_rename_default_profile_to_existing_name(profile_manager: ProfileManager):
    """重命名默认账号为已占用名称会抛出 ValueError。"""
    profile_manager.load()
    profile_manager.switch_profile("other")
    with pytest.raises(ValueError, match="已存在"):
        profile_manager.rename_profile("default", "other")


def test_rename_profile_to_same_name_is_noop(profile_manager: ProfileManager):
    """同名重命名是无操作，不报错、不写盘。"""
    profile_manager.load()
    profile = profile_manager.rename_profile("default", "default")
    assert profile.name == "default"
    assert profile_manager.get_collection().default_profile == "default"


def test_load_legacy_file_without_default_profile(temp_profiles_file: Path):
    """旧版配置文件（无 default_profile 字段）加载后兼容为新默认账号。"""
    temp_profiles_file.write_text(
        json.dumps(
            {
                "version": 1,
                "active_profile": "default",
                "profiles": {
                    "default": {
                        "version": 1,
                        "name": "default",
                        "treasure_matrix": [],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manager = ProfileManager(temp_profiles_file)
    manager.load()
    collection = manager.get_collection()
    assert collection.default_profile == "default"
    assert "default" in collection.profiles


def test_load_self_heals_missing_default_profile(temp_profiles_file: Path):
    """default_profile 悬空但存在 'default' 账号时，回退复用它。

    不能凭空造一个空账号：那个账号既没有数据，又会因保留名校验而无法切换，
    同时把真正有数据的 'default' 变成永远访问不到的僵尸条目。
    """
    temp_profiles_file.write_text(
        json.dumps(
            {
                "version": 1,
                "active_profile": "default",
                "default_profile": "我的账号",
                "profiles": {
                    "default": {
                        "version": 1,
                        "name": "default",
                        "treasure_matrix": [],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manager = ProfileManager(temp_profiles_file)
    manager.load()
    collection = manager.get_collection()
    assert collection.default_profile == "default"
    assert "我的账号" not in collection.profiles
    # 回退后默认账号可正常切换，不会被保留名校验挡住
    manager.switch_profile("default")
    assert manager.get_active_profile_name() == "default"


def test_load_creates_default_when_no_candidate(temp_profiles_file: Path):
    """default_profile 悬空且没有 'default' 账号时，回退并创建默认账号。"""
    temp_profiles_file.write_text(
        json.dumps(
            {
                "version": 1,
                "active_profile": "alt",
                "default_profile": "我的账号",
                "profiles": {
                    "alt": {"version": 1, "name": "alt", "treasure_matrix": []}
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manager = ProfileManager(temp_profiles_file)
    manager.load()
    collection = manager.get_collection()
    assert collection.default_profile == "default"
    assert "default" in collection.profiles
    assert "我的账号" not in collection.profiles


def test_switch_to_reserved_default_name_after_rename(
    profile_manager: ProfileManager,
):
    """默认账号改名后，不能新建/切换到保留名称 'default'。"""
    profile_manager.load()
    profile_manager.rename_profile("default", "我的账号")
    with pytest.raises(ValueError, match="保留名称"):
        profile_manager.switch_profile("default")


def test_rename_profile_to_reserved_default_name(profile_manager: ProfileManager):
    """默认账号改名后，其它账号不能改名为保留名称 'default'。"""
    profile_manager.load()
    profile_manager.rename_profile("default", "我的账号")
    profile_manager.switch_profile("other")
    with pytest.raises(ValueError, match="保留名称"):
        profile_manager.rename_profile("other", "default")


def test_rename_default_profile_back_to_default(profile_manager: ProfileManager):
    """回归：默认账号可以改回 'default'，否则改名操作无法撤销。"""
    profile_manager.load()
    profile_manager.rename_profile("default", "我的账号")

    profile = profile_manager.rename_profile("我的账号", "default")

    collection = profile_manager.get_collection()
    assert profile.name == "default"
    assert collection.default_profile == "default"
    assert collection.active_profile == "default"
    assert "我的账号" not in collection.profiles


def test_switch_default_name_allowed_when_default_not_renamed(
    profile_manager: ProfileManager,
):
    """未改名的默认账号下，切换回 'default' 仍然允许。"""
    profile_manager.load()
    profile_manager.switch_profile("other")
    profile_manager.switch_profile("default")
    assert profile_manager.get_active_profile_name() == "default"


def test_treasure_matrix_operations(profile_manager: ProfileManager):
    """测试宝藏基质的 CRUD 操作。"""
    profile_manager.load()
    entry1 = TreasureMatrixEntry(
        weapon_id="wpn_001",
        weapon_name="Test Weapon 1",
        affix1_level=3,
        affix2_level=4,
        affix3_level=2,
    )
    entry2 = TreasureMatrixEntry(
        weapon_id="wpn_002",
        weapon_name="Test Weapon 2",
        affix1_level=5,
        affix2_level=6,
        affix3_level=3,
    )

    # 添加条目
    profile_manager.add_treasure_matrix_entry(entry1)
    profile_manager.add_treasure_matrix_entry(entry2)
    matrix = profile_manager.get_active_profile().treasure_matrix
    assert len(matrix) == 2

    # 更新现有条目
    entry1_updated = TreasureMatrixEntry(
        weapon_id="wpn_001",
        weapon_name="Test Weapon 1 Updated",
        affix1_level=6,
        affix2_level=6,
        affix3_level=3,
    )
    profile_manager.add_treasure_matrix_entry(entry1_updated)
    matrix = profile_manager.get_active_profile().treasure_matrix
    assert len(matrix) == 2
    updated = next(e for e in matrix if e.weapon_id == "wpn_001")
    assert updated.affix1_level == 6

    # 移除条目
    profile_manager.remove_treasure_matrix_entry("wpn_001")
    matrix = profile_manager.get_active_profile().treasure_matrix
    assert len(matrix) == 1
    assert matrix[0].weapon_id == "wpn_002"


def test_update_weapon_priority_without_matrix(profile_manager: ProfileManager):
    """测试未拥有宝藏基质的武器也可以保存优先级。"""
    profile_manager.load()

    profile = profile_manager.update_weapon_priority("wpn_003", 7)
    assert profile.weapon_priorities["wpn_003"] == 7
    assert profile.treasure_matrix == []

    profile = profile_manager.update_weapon_priority("wpn_003", 0)
    assert "wpn_003" not in profile.weapon_priorities


def test_update_treasure_matrix_keeps_unowned_priorities(
    profile_manager: ProfileManager,
):
    """回归：更新矩阵不得清空未拥有武器的优先级。

    `update_weapon_priority` 明确支持给未拥有基质的武器设优先级，而调整任意
    一把已拥有武器的等级都会触发 `update_treasure_matrix` 全量提交；两者的
    契约必须自洽，否则用户的优先级设置会在日常操作中静默丢失。
    """
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="owned", weapon_name="O", affix1_level=1)
    )
    profile_manager.update_weapon_priority("owned", 9)
    profile_manager.update_weapon_priority("unowned", 7)

    entries = profile_manager.get_active_profile().treasure_matrix
    entries[0].affix1_level = 3
    profile = profile_manager.update_treasure_matrix(entries)

    assert profile.weapon_priorities["unowned"] == 7
    assert profile.weapon_priorities["owned"] == 9


def test_update_treasure_matrix_clears_zeroed_priority(profile_manager: ProfileManager):
    """矩阵内条目 priority 归零时，应从 weapon_priorities 中移除。"""
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W1", affix1_level=1)
    )
    profile_manager.update_weapon_priority("wpn_001", 5)

    entries = profile_manager.get_active_profile().treasure_matrix
    entries[0].priority = 0
    profile = profile_manager.update_treasure_matrix(entries)

    assert "wpn_001" not in profile.weapon_priorities


def test_update_treasure_matrix_keeps_removed_entry_priority(
    profile_manager: ProfileManager,
):
    """条目移出矩阵后优先级仍保留：优先级是独立于"是否拥有基质"的用户偏好。

    与 `remove_treasure_matrix_entry` 的既有行为保持一致。
    """
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W1", affix1_level=1)
    )
    profile_manager.update_weapon_priority("wpn_001", 5)

    profile = profile_manager.update_treasure_matrix([])
    assert profile.weapon_priorities["wpn_001"] == 5


def test_entry_priority_is_projection_of_weapon_priorities(
    profile_manager: ProfileManager,
):
    """entry.priority 始终是 weapon_priorities 的投影，两者不会各说各话。

    优先级只有 weapon_priorities 一个权威来源；条目上的 priority 只为方便
    前端就近读取而存在，任何写路径之后都必须与权威源一致。
    """
    profile_manager.load()
    profile_manager.update_weapon_priority("wpn_001", 8)
    # 后设置优先级，再加入矩阵：条目应当继承既有的手动优先级
    profile = profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W1", affix1_level=1)
    )
    assert profile.treasure_matrix[0].priority == 8

    # 清除手动优先级后，投影同步归零
    profile = profile_manager.update_weapon_priority("wpn_001", 0)
    assert profile.weapon_priorities == {}
    assert profile.treasure_matrix[0].priority == 0


def test_add_entry_does_not_override_existing_manual_priority(
    profile_manager: ProfileManager,
):
    """新增条目自带的 priority 不得覆盖用户已设置的手动优先级。"""
    profile_manager.load()
    profile_manager.update_weapon_priority("wpn_001", 8)

    profile = profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(
            weapon_id="wpn_001", weapon_name="W1", affix1_level=1, priority=2
        )
    )

    assert profile.weapon_priorities["wpn_001"] == 8
    assert profile.treasure_matrix[0].priority == 8


def test_persistence(temp_profiles_file: Path):
    """测试账号配置持久化到磁盘。"""
    manager1 = ProfileManager(temp_profiles_file)
    manager1.load()
    manager1.switch_profile("test")
    manager1.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="Test")
    )

    # 创建新管理器并从同一文件加载
    manager2 = ProfileManager(temp_profiles_file)
    manager2.load()
    assert manager2.get_active_profile_name() == "test"
    assert len(manager2.get_active_profile().treasure_matrix) == 1


def test_sync_treasure_matrix_entries_saves_once(
    profile_manager: ProfileManager, monkeypatch: pytest.MonkeyPatch
):
    """批量同步多把新武器时，只执行一次持久化。"""
    profile_manager.load()
    save_count = 0

    def fake_save(*args, **kwargs):
        nonlocal save_count
        save_count += 1
        return True

    monkeypatch.setattr(profile_manager_module, "_save_profiles_to_file", fake_save)

    result = profile_manager.sync_treasure_matrix_entries(
        [
            TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="Weapon 1"),
            TreasureMatrixEntry(weapon_id="wpn_002", weapon_name="Weapon 2"),
            TreasureMatrixEntry(weapon_id="wpn_003", weapon_name="Weapon 3"),
        ]
    )

    assert [entry.weapon_id for entry in result.added] == [
        "wpn_001",
        "wpn_002",
        "wpn_003",
    ]
    assert result.updated == []
    assert save_count == 1
    assert len(profile_manager.get_active_profile().treasure_matrix) == 3


def test_sync_treasure_matrix_entries_updates_only_higher_levels(
    profile_manager: ProfileManager, monkeypatch: pytest.MonkeyPatch
):
    """扫描同步只提升等级，不用较低扫描结果覆盖用户已有数据。"""
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(
            weapon_id="wpn_001",
            weapon_name="Weapon 1",
            affix1_level=3,
            affix2_level=3,
            affix3_level=2,
            include_in_calculation=True,
        )
    )
    save_count = 0

    def fake_save(*args, **kwargs):
        nonlocal save_count
        save_count += 1
        return True

    monkeypatch.setattr(profile_manager_module, "_save_profiles_to_file", fake_save)

    no_change = profile_manager.sync_treasure_matrix_entries(
        [
            TreasureMatrixEntry(
                weapon_id="wpn_001",
                weapon_name="Weapon 1",
                affix1_level=2,
                affix2_level=3,
                affix3_level=1,
            )
        ]
    )
    assert no_change.added == []
    assert no_change.updated == []
    assert save_count == 0

    changed = profile_manager.sync_treasure_matrix_entries(
        [
            TreasureMatrixEntry(
                weapon_id="wpn_001",
                weapon_name="Weapon 1",
                affix1_level=6,
                affix2_level=6,
                affix3_level=3,
            )
        ]
    )

    entry = profile_manager.get_active_profile().treasure_matrix[0]
    assert changed.added == []
    assert [updated.weapon_id for updated in changed.updated] == ["wpn_001"]
    assert (entry.affix1_level, entry.affix2_level, entry.affix3_level) == (6, 6, 3)
    assert entry.include_in_calculation is False
    assert save_count == 1


def test_clear_profile_data_active(profile_manager: ProfileManager):
    """清空激活账号：treasure_matrix 与 weapon_priorities 清空，其它保留。"""
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W1", affix1_level=3)
    )
    profile_manager.update_weapon_priority("wpn_001", 5)
    profile_manager.update_weapon_overview_filters(
        {"3star": False, "4star": True, "5star": True, "6star": True, "custom": True}
    )
    profile_manager.update_matrix_planner_farming_locations(
        {"world_energy_point_group01": False, "world_energy_point_group02": True}
    )

    cleared = profile_manager.clear_profile_data()

    assert cleared.treasure_matrix == []
    assert cleared.weapon_priorities == {}
    # 展示偏好（过滤器、刷取地点筛选）、名称与版本保留
    assert cleared.weapon_overview_filters["3star"] is False
    assert cleared.matrix_planner_farming_locations == {
        "world_energy_point_group01": False,
        "world_energy_point_group02": True,
    }
    assert cleared.name == "default"
    assert cleared.version == 1


def test_update_matrix_planner_farming_locations_persists(
    profile_manager: ProfileManager, temp_profiles_file: Path
):
    """刷取地点筛选更新后立即落盘，重新加载后保持不变。"""
    profile_manager.load()
    locations = {
        "world_energy_point_group01": True,
        "world_energy_point_group02": False,
    }

    profile = profile_manager.update_matrix_planner_farming_locations(locations)

    assert profile.matrix_planner_farming_locations == locations
    data = json.loads(temp_profiles_file.read_text(encoding="utf-8"))
    assert data["profiles"]["default"]["matrix_planner_farming_locations"] == locations

    reloaded = ProfileManager(temp_profiles_file)
    reloaded.load()
    assert reloaded.get_active_profile().matrix_planner_farming_locations == locations


def test_update_matrix_planner_farming_locations_defaults_empty(
    profile_manager: ProfileManager,
):
    """未设置过刷取地点筛选时默认为空字典（前端视缺失键为全部勾选）。"""
    profile_manager.load()
    assert profile_manager.get_active_profile().matrix_planner_farming_locations == {}


def test_clear_profile_data_named_keeps_active(profile_manager: ProfileManager):
    """按名清空非激活账号时，不改变当前激活账号。"""
    profile_manager.load()
    # 给 default 加数据
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_default", weapon_name="D", affix1_level=2)
    )
    # 切换到 alt 并加数据
    profile_manager.switch_profile("alt")
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_alt", weapon_name="A", affix1_level=4)
    )

    cleared = profile_manager.clear_profile_data("default")

    assert cleared.name == "default"
    assert cleared.treasure_matrix == []
    # 激活账号仍为 alt，且其数据未受影响
    assert profile_manager.get_active_profile_name() == "alt"
    alt = profile_manager.get_collection().profiles["alt"]
    assert [e.weapon_id for e in alt.treasure_matrix] == ["wpn_alt"]


def test_clear_profile_data_nonexistent(profile_manager: ProfileManager):
    """清空不存在的账号会抛出 ValueError。"""
    profile_manager.load()
    with pytest.raises(ValueError, match="不存在"):
        profile_manager.clear_profile_data("no_such_profile")


def test_clear_profile_data_save_failure_keeps_memory(
    profile_manager: ProfileManager, monkeypatch: pytest.MonkeyPatch
):
    """保存失败时内存数据不能被清空。"""
    profile_manager.load()
    profile_manager.add_treasure_matrix_entry(
        TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W1", affix1_level=3)
    )

    def fake_save(*args, **kwargs):
        raise ProfileSaveError("disk full")

    monkeypatch.setattr(profile_manager_module, "_save_profiles_to_file", fake_save)

    with pytest.raises(ProfileSaveError):
        profile_manager.clear_profile_data()

    entries = profile_manager.get_active_profile().treasure_matrix
    assert [e.weapon_id for e in entries] == ["wpn_001"]


# --- 自定义基质稳定 ID 迁移 ---


def _seed_legacy_custom_refs(manager: ProfileManager) -> None:
    """写入一份使用旧格式 custom_stat_{下标} 的账号数据。"""
    manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom_stat_0", weapon_name="C0", affix1_level=3, priority=5
            ),
            TreasureMatrixEntry(
                weapon_id="custom_stat_2", weapon_name="C2", affix1_level=2
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1, priority=4
            ),
        ]
    )


def test_migrate_custom_stat_ids_rewrites_refs(profile_manager: ProfileManager):
    """旧格式引用按下标改写为 custom:{id}，普通武器不受影响。"""
    profile_manager.load()
    _seed_legacy_custom_refs(profile_manager)

    changed = profile_manager.migrate_custom_stat_ids(["aaa", "bbb", "ccc"])

    profile = profile_manager.get_active_profile()
    assert changed is True
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "custom:aaa",
        "custom:ccc",
        "wpn_normal",
    ]
    # 优先级映射的 key 同步改写，值不变
    assert profile.weapon_priorities == {"custom:aaa": 5, "wpn_normal": 4}


def test_migrate_custom_stat_ids_drops_orphans(profile_manager: ProfileManager):
    """下标越界的孤儿引用被丢弃，不留成幽灵条目。"""
    profile_manager.load()
    _seed_legacy_custom_refs(profile_manager)

    # 配置里只剩一个自定义基质：custom_stat_2 已无对应项
    profile_manager.migrate_custom_stat_ids(["only"])

    profile = profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "custom:only",
        "wpn_normal",
    ]
    assert "custom:only" in profile.weapon_priorities


def test_migrate_custom_stat_ids_is_idempotent(profile_manager: ProfileManager):
    """迁移可重复执行：第二次不再产生变更（每次启动都会调用）。"""
    profile_manager.load()
    _seed_legacy_custom_refs(profile_manager)

    assert profile_manager.migrate_custom_stat_ids(["aaa", "bbb", "ccc"]) is True
    before = profile_manager.get_active_profile().model_dump()

    assert profile_manager.migrate_custom_stat_ids(["aaa", "bbb", "ccc"]) is False
    assert profile_manager.get_active_profile().model_dump() == before


def test_migrate_custom_stat_ids_covers_all_profiles(profile_manager: ProfileManager):
    """迁移覆盖全部账号，而不只是当前激活账号。"""
    profile_manager.load()
    profile_manager.switch_profile("alt")
    _seed_legacy_custom_refs(profile_manager)
    profile_manager.switch_profile("default")
    _seed_legacy_custom_refs(profile_manager)

    profile_manager.migrate_custom_stat_ids(["aaa", "bbb", "ccc"])

    for name in ("default", "alt"):
        ids = [
            e.weapon_id
            for e in profile_manager.get_collection().profiles[name].treasure_matrix
        ]
        assert ids == ["custom:aaa", "custom:ccc", "wpn_normal"]


def test_migrate_custom_stat_ids_no_custom_refs(profile_manager: ProfileManager):
    """没有旧格式引用时不写盘。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W", affix1_level=1)]
    )

    assert profile_manager.migrate_custom_stat_ids(["aaa"]) is False


# --- 内置武器 ID 变更迁移 ---


def _seed_stale_weapon_refs(manager: ProfileManager) -> None:
    """写入一份含旧中文 ID 引用与正常引用的账号数据。"""
    manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="曜夜的首演",
                weapon_name="曜夜的首演",
                affix1_level=5,
                priority=6,
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_sword_0001",
                weapon_name="测试武器",
                affix1_level=2,
                priority=3,
            ),
        ]
    )


def test_migrate_stale_weapon_ids_rewrites_by_name(profile_manager: ProfileManager):
    """旧中文 ID 按缓存的武器名称改写为最新 ID。"""
    profile_manager.load()
    _seed_stale_weapon_refs(profile_manager)

    changed = profile_manager.migrate_stale_weapon_ids(
        {"曜夜的首演": "wpn_lance_0101", "测试武器": "wpn_sword_0001"}
    )

    profile = profile_manager.get_active_profile()
    assert changed is True
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "wpn_lance_0101",
        "wpn_sword_0001",
    ]
    # 优先级映射的 key 同步改写，值不变
    assert profile.weapon_priorities == {"wpn_lance_0101": 6, "wpn_sword_0001": 3}


def test_migrate_stale_weapon_ids_uses_id_as_name_fallback(
    profile_manager: ProfileManager,
):
    """未缓存名称时，用旧 ID 本身当名称匹配（旧中文 ID 即武器名）。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [TreasureMatrixEntry(weapon_id="曜夜的首演", affix1_level=4)]
    )

    assert (
        profile_manager.migrate_stale_weapon_ids({"曜夜的首演": "wpn_lance_0101"})
        is True
    )

    profile = profile_manager.get_active_profile()
    assert profile.treasure_matrix[0].weapon_id == "wpn_lance_0101"


def test_migrate_stale_weapon_ids_keeps_unmatched_refs(
    profile_manager: ProfileManager,
):
    """游戏中已不存在且名称对不上的引用保持原样，不丢弃用户数据。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="wpn_removed", weapon_name="旧武器", affix1_level=2
            )
        ]
    )

    assert profile_manager.migrate_stale_weapon_ids({}) is False

    profile = profile_manager.get_active_profile()
    assert profile.treasure_matrix[0].weapon_id == "wpn_removed"


def test_migrate_stale_weapon_ids_skips_custom_refs(profile_manager: ProfileManager):
    """自定义基质引用不属于本迁移范围，保持原样。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom:abc123", weapon_name="自定", affix1_level=3
            )
        ]
    )

    assert profile_manager.migrate_stale_weapon_ids({}) is False

    profile = profile_manager.get_active_profile()
    assert profile.treasure_matrix[0].weapon_id == "custom:abc123"


def test_migrate_stale_weapon_ids_is_idempotent(profile_manager: ProfileManager):
    """迁移可重复执行：第二次不再产生变更（每次启动都会调用）。"""
    profile_manager.load()
    _seed_stale_weapon_refs(profile_manager)
    weapons_by_name = {"曜夜的首演": "wpn_lance_0101", "测试武器": "wpn_sword_0001"}

    assert profile_manager.migrate_stale_weapon_ids(weapons_by_name) is True
    before = profile_manager.get_active_profile().model_dump()

    assert profile_manager.migrate_stale_weapon_ids(weapons_by_name) is False
    assert profile_manager.get_active_profile().model_dump() == before


def test_migrate_stale_weapon_ids_covers_all_profiles(
    profile_manager: ProfileManager,
):
    """迁移覆盖全部账号，而不只是当前激活账号。"""
    profile_manager.load()
    profile_manager.switch_profile("alt")
    _seed_stale_weapon_refs(profile_manager)
    profile_manager.switch_profile("default")
    _seed_stale_weapon_refs(profile_manager)

    profile_manager.migrate_stale_weapon_ids({"曜夜的首演": "wpn_lance_0101"})

    for name in ("default", "alt"):
        ids = [
            e.weapon_id
            for e in profile_manager.get_collection().profiles[name].treasure_matrix
        ]
        assert ids == ["wpn_lance_0101", "wpn_sword_0001"]


def test_prune_custom_stat_refs_cleans_all_profiles(profile_manager: ProfileManager):
    """空白名单清理自定义引用：覆盖全部账号的矩阵与优先级，普通武器不受影响。"""
    profile_manager.load()
    profile_manager.switch_profile("alt")
    _seed_legacy_custom_refs(profile_manager)
    profile_manager.switch_profile("default")
    _seed_legacy_custom_refs(profile_manager)

    assert profile_manager.prune_custom_stat_refs(set()) is True

    for name in ("default", "alt"):
        profile = profile_manager.get_collection().profiles[name]
        assert [e.weapon_id for e in profile.treasure_matrix] == ["wpn_normal"]
        assert profile.weapon_priorities == {"wpn_normal": 4}


def test_prune_custom_stat_refs_cleans_new_format(profile_manager: ProfileManager):
    """新格式 custom:{id} 引用同样被清理。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom:abc123", weapon_name="C", affix1_level=3, priority=5
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1
            ),
        ]
    )

    assert profile_manager.prune_custom_stat_refs(set()) is True

    profile = profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == ["wpn_normal"]
    assert profile.weapon_priorities == {}


def test_prune_custom_stat_refs_no_custom_refs(profile_manager: ProfileManager):
    """没有自定义引用时不写盘。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [TreasureMatrixEntry(weapon_id="wpn_001", weapon_name="W", affix1_level=1)]
    )

    assert profile_manager.prune_custom_stat_refs(set()) is False


def test_prune_custom_stat_refs_keeps_live_ids(profile_manager: ProfileManager):
    """白名单内的引用保留，只有配置里已删除的那条被剪掉。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom:live", weapon_name="L", affix1_level=3, priority=5
            ),
            TreasureMatrixEntry(
                weapon_id="custom:gone", weapon_name="G", affix1_level=2, priority=3
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1, priority=4
            ),
        ]
    )

    assert profile_manager.prune_custom_stat_refs({"live"}) is True

    profile = profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "custom:live",
        "wpn_normal",
    ]
    assert profile.weapon_priorities == {"custom:live": 5, "wpn_normal": 4}


def test_prune_custom_stat_refs_all_ids_live(profile_manager: ProfileManager):
    """全部引用都在白名单内时不写盘——设置页每次改动都会调用，不能有无谓写入。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom:live", weapon_name="L", affix1_level=3, priority=5
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1
            ),
        ]
    )

    assert profile_manager.prune_custom_stat_refs({"live", "unused"}) is False


def test_prune_custom_stat_refs_drops_legacy_refs(profile_manager: ProfileManager):
    """旧格式引用一律剪掉：启动迁移之后还残留的必然解析不出对应条目。"""
    profile_manager.load()
    _seed_legacy_custom_refs(profile_manager)

    assert profile_manager.prune_custom_stat_refs({"aaa", "bbb", "ccc"}) is True

    profile = profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == ["wpn_normal"]
    assert profile.weapon_priorities == {"wpn_normal": 4}


def test_prune_custom_stat_refs_cleans_orphan_priority_only(
    profile_manager: ProfileManager,
):
    """矩阵里没有孤儿、只有优先级键是孤儿时也要清理。"""
    profile_manager.load()
    profile_manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1, priority=4
            )
        ]
    )
    profile_manager.update_weapon_priority("custom:gone", 7)

    assert profile_manager.prune_custom_stat_refs(set()) is True

    profile = profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == ["wpn_normal"]
    assert profile.weapon_priorities == {"wpn_normal": 4}
