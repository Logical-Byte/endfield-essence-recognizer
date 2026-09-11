import json

import pytest
from pydantic import ValidationError

from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.schemas.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)


@pytest.fixture
def settings_file(tmp_path):
    return tmp_path / "settings.json"


@pytest.fixture
def manager(settings_file):
    return UserSettingManager(settings_file)


def test_manager_initial_state(manager, settings_file):
    """测试 UserSettingManager 的初始状态。"""
    assert manager._user_setting_file == settings_file
    assert isinstance(manager.get_user_setting(), UserSetting)


def test_get_user_setting_returns_copy(manager):
    """测试 get_user_setting 返回配置的深拷贝。"""
    s1 = manager.get_user_setting()
    s2 = manager.get_user_setting()
    assert s1 == s2
    assert s1 is not s2


def test_load_user_setting_file_not_exists(manager, settings_file):
    """测试从不存在的文件加载时创建默认配置文件。"""
    assert not settings_file.exists()
    manager.load_user_setting()
    assert settings_file.exists()
    # 应该是默认配置
    assert manager.get_user_setting().trash_weapon_ids == []


def test_load_user_setting_valid_file(manager, settings_file):
    """测试有效的配置文件能正确加载到内存。"""
    data = {
        "version": UserSetting._VERSION,
        "trash_weapon_ids": ["weapon_1"],
        "treasure_essence_stats": [
            {
                "name": "自定义基质",
                "attribute": "atk",
                "secondary": "crit",
                "skill": None,
            }
        ],
    }
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    manager.load_user_setting()
    setting = manager.get_user_setting()
    assert setting.trash_weapon_ids == ["weapon_1"]
    assert len(setting.treasure_essence_stats) == 1
    assert setting.treasure_essence_stats[0].attribute == "atk"
    assert setting.treasure_essence_stats[0].name == "自定义基质"


def test_load_user_setting_invalid_version_backups_file(manager, settings_file):
    """测试无效版本的文件被备份并替换为默认配置。"""
    data = {
        "version": -1,  # 错误版本
        "trash_weapon_ids": ["old_weapon"],
    }
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    manager.load_user_setting()

    # 检查备份文件存在（带时间戳）
    backup_files = list(settings_file.parent.glob("settings.backup.*.json"))
    assert len(backup_files) == 1
    backup_file = backup_files[0]
    assert json.loads(backup_file.read_text(encoding="utf-8"))["trash_weapon_ids"] == [
        "old_weapon"
    ]

    # 当前配置应该是默认值
    assert manager.get_user_setting().trash_weapon_ids == []
    # 新文件应该已保存默认配置
    assert settings_file.exists()
    assert (
        json.loads(settings_file.read_text(encoding="utf-8"))["version"]
        == UserSetting._VERSION
    )


def test_load_user_setting_corrupt_json_backups_file(manager, settings_file):
    """测试损坏的 JSON 文件被备份并替换为默认配置。"""
    settings_file.write_text("not a json", encoding="utf-8")

    manager.load_user_setting()

    # 检查备份文件存在（带时间戳）
    backup_files = list(settings_file.parent.glob("settings.backup.*.json"))
    assert len(backup_files) == 1
    backup_file = backup_files[0]
    assert backup_file.read_text(encoding="utf-8") == "not a json"

    assert manager.get_user_setting().version == UserSetting._VERSION


def test_update_from_dict_version_mismatch(manager):
    """测试 update_from_dict 在版本不匹配时抛出 ConfigVersionMismatchError。"""
    data = {"version": -1, "trash_weapon_ids": ["test"]}
    with pytest.raises(ConfigVersionMismatchError) as excinfo:
        manager.update_from_dict(data)
    assert excinfo.value.expected == UserSetting._VERSION
    assert excinfo.value.got == -1


def test_update_from_user_setting_version_mismatch(manager):
    """测试 update_from_user_setting 在版本不匹配时抛出 ConfigVersionMismatchError。"""
    other = UserSetting()
    other.version = -1
    with pytest.raises(ConfigVersionMismatchError) as excinfo:
        manager.update_from_user_setting(other)
    assert excinfo.value.expected == UserSetting._VERSION
    assert excinfo.value.got == -1


def test_save_user_setting(manager, settings_file):
    """测试 save_user_setting 能正确将内存中的配置持久化到磁盘。"""
    # 访问私有成员用于测试设置
    setting = manager._user_setting
    setting.trash_weapon_ids = ["test_save"]
    manager.save_user_setting()

    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["trash_weapon_ids"] == ["test_save"]


def test_update_from_dict(manager, settings_file):
    """测试 update_from_dict 更新配置并保存到磁盘。"""
    manager.update_from_dict({"trash_weapon_ids": ["dict_update"]})
    assert manager.get_user_setting().trash_weapon_ids == ["dict_update"]
    assert json.loads(settings_file.read_text(encoding="utf-8"))[
        "trash_weapon_ids"
    ] == ["dict_update"]


def test_update_from_user_setting(manager, settings_file):
    """测试 update_from_user_setting 更新配置并保存到磁盘。"""
    new_setting = UserSetting(trash_weapon_ids=["model_update"])
    manager.update_from_user_setting(new_setting)
    assert manager.get_user_setting().trash_weapon_ids == ["model_update"]
    assert json.loads(settings_file.read_text(encoding="utf-8"))[
        "trash_weapon_ids"
    ] == ["model_update"]


def test_ensure_custom_stat_ids_assigns_missing(manager):
    """旧配置中缺失的自定义基质 ID 会被补齐，且顺序即迁移映射的下标。"""
    manager.update_from_dict(
        {
            "treasure_essence_stats": [
                {"name": "A", "attribute": "a1", "secondary": None, "skill": None},
                {"name": "B", "attribute": "a2", "secondary": None, "skill": None},
            ]
        }
    )

    stats = manager.get_user_setting().treasure_essence_stats
    ids = manager.get_custom_stat_ids()
    assert all(s.id for s in stats)
    assert len(set(ids)) == 2
    assert ids == [stats[0].id, stats[1].id]


def test_ensure_custom_stat_ids_preserves_existing(manager):
    """已有 ID 不被改写：profile 中的引用依赖它保持稳定。"""
    manager.update_from_dict(
        {
            "treasure_essence_stats": [
                {"id": "fixed", "name": "A", "attribute": "a1"},
            ]
        }
    )
    assert manager.get_custom_stat_ids() == ["fixed"]

    # 再次写入（例如用户改了名称）不应换 ID
    manager.update_from_dict(
        {
            "treasure_essence_stats": [
                {"id": "fixed", "name": "改名后", "attribute": "a1"},
            ]
        }
    )
    assert manager.get_custom_stat_ids() == ["fixed"]


def test_ensure_custom_stat_ids_dedupes(manager):
    """手工编辑造成的重复 ID 会被重新分配，避免两个条目互相顶替。"""
    manager.update_from_dict(
        {
            "treasure_essence_stats": [
                {"id": "dup", "name": "A"},
                {"id": "dup", "name": "B"},
            ]
        }
    )
    ids = manager.get_custom_stat_ids()
    assert len(set(ids)) == 2
    assert ids[0] == "dup"


def test_reset_to_default(manager, settings_file):
    """测试 reset_to_default 将配置重置为默认值并保存到磁盘。"""
    manager.update_from_dict(
        {
            "trash_weapon_ids": ["w1", "w2"],
            "treasure_essence_stats": [
                {"name": "自定义", "attribute": "atk", "secondary": None, "skill": None}
            ],
            "high_level_treasure_enabled": True,
        }
    )

    returned = manager.reset_to_default()

    # 返回值与内存均为默认配置
    assert returned == UserSetting()
    assert manager.get_user_setting() == UserSetting()
    # 磁盘已落默认值
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["version"] == UserSetting._VERSION
    assert data["trash_weapon_ids"] == []
    assert data["treasure_essence_stats"] == []
    assert data["high_level_treasure_enabled"] is False


def test_update_from_dict_invalid_data(manager):
    """测试 update_from_dict 在提供无效数据时抛出异常。"""
    with pytest.raises(ValidationError):
        manager.update_from_dict({"trash_weapon_ids": "not a list"})


def test_config_migration_invalid_version():
    """测试无效版本号迁移失败"""
    from endfield_essence_recognizer.schemas.user_setting import UserSetting

    # 负数版本
    with pytest.raises(ValueError, match="无效的配置版本"):
        UserSetting.migrate_from_old_version({"version": -1})

    # 未来版本
    with pytest.raises(ValueError, match="配置文件版本过高"):
        UserSetting.migrate_from_old_version({"version": 999})


def test_load_user_setting_with_migration(manager, settings_file):
    """测试加载旧版本配置时自动迁移"""
    old_config = {
        "version": 3,
        "trash_weapon_ids": ["old_weapon"],
        "treasure_essence_stats": [],
        "treasure_action": "lock",
        "trash_action": "unlock",
        "non_five_star_behavior": "process",
        "high_level_treasure_enabled": False,
        "high_level_treasure_attribute_threshold": 3,
        "high_level_treasure_secondary_threshold": 3,
        "high_level_treasure_skill_threshold": 3,
        "auto_page_flip": True,
    }
    settings_file.write_text(json.dumps(old_config), encoding="utf-8")

    manager.load_user_setting()

    # 验证迁移成功
    setting = manager.get_user_setting()
    assert setting.version == UserSetting._VERSION
    assert setting.trash_weapon_ids == ["old_weapon"]
    assert setting.update_mirror == "github"
    assert setting.update_proxy == ""

    # 验证新版本已保存到文件
    saved_data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved_data["version"] == UserSetting._VERSION
    assert saved_data["update_mirror"] == "github"


def test_user_setting_schema_stability():
    """检测 UserSetting schema 变更，提醒开发者更新迁移逻辑"""
    expected_fields = {
        "version",
        "trash_weapon_ids",
        "treasure_essence_stats",
        "treasure_essence_match_mode",
        "treasure_action",
        "trash_action",
        "non_five_star_behavior",
        "high_level_treasure_enabled",
        "high_level_treasure_attribute_threshold",
        "high_level_treasure_secondary_threshold",
        "high_level_treasure_skill_threshold",
        "high_level_treasure_match_mode",
        "high_level_treasure_sum_threshold",
        "high_level_treasure_only_check_attribute",
        "high_level_treasure_only_check_secondary",
        "high_level_treasure_only_check_skill",
        "non_five_star_separate_high_level_settings",
        "non_five_star_high_level_attribute_threshold",
        "non_five_star_high_level_secondary_threshold",
        "non_five_star_high_level_skill_threshold",
        "non_five_star_high_level_match_mode",
        "non_five_star_high_level_sum_threshold",
        "non_five_star_high_level_only_check_attribute",
        "non_five_star_high_level_only_check_secondary",
        "non_five_star_high_level_only_check_skill",
        "same_type_treasure_limit_enabled",
        "same_type_treasure_limit",
        "same_type_group_mode",
        "same_type_keep_best",
        "same_type_keep_best_mode",
        "same_type_non_downgrade_filter",
        "redundant_cleanup_enabled",
        "redundant_cleanup_trigger",
        "redundant_action",
        "auto_page_flip",
        "fix_grid_row_offset_after_page_flip",
        "fix_page_flip_overscroll",
        "update_mirror",
        "update_flow",
        "update_github_mirror",
        "update_proxy",
        "update_mirrorchyan_res_id",
        "update_mirrorchyan_cdk",
        "update_mirrorchyan_user_agent",
    }

    actual_fields = set(UserSetting.model_fields.keys())

    # 如果字段变化，测试失败并提示
    assert actual_fields == expected_fields, (
        f"UserSetting schema 已变更！\n"
        f"新增字段: {actual_fields - expected_fields}\n"
        f"删除字段: {expected_fields - actual_fields}\n"
        f"请执行以下步骤：\n"
        f"1. 更新 UserSetting._VERSION\n"
        f"2. 在 migrate_from_old_version() 添加迁移逻辑\n"
        f"3. 添加对应的迁移测试\n"
        f"4. 更新此测试的 expected_fields"
    )


def test_essence_stats_schema_stability():
    """检测 EssenceStats schema 变更，提醒开发者更新迁移逻辑"""
    from endfield_essence_recognizer.schemas.user_setting import EssenceStats

    expected_fields = {
        "id",
        "name",
        "attribute",
        "secondary",
        "skill",
        "no_prompt_switch",
    }

    actual_fields = set(EssenceStats.model_fields.keys())

    assert actual_fields == expected_fields, (
        f"EssenceStats schema 已变更！\n"
        f"新增字段: {actual_fields - expected_fields}\n"
        f"删除字段: {expected_fields - actual_fields}\n"
        f"请执行以下步骤：\n"
        f"1. 更新 UserSetting._VERSION\n"
        f"2. 在 _migrate_v{UserSetting._VERSION - 1}_to_v{UserSetting._VERSION}() 添加迁移逻辑\n"
        f"3. 添加对应的迁移测试\n"
        f"4. 更新此测试的 expected_fields"
    )


def test_config_migration_chain_v2_to_current():
    """测试跨版本链式迁移：v2 → 当前版本（早期 v2，缺少后期新增字段）

    注意：此测试主要验证迁移链的完整性，不验证所有字段的默认值。
    字段遗漏检测由 test_migration_sets_all_required_fields 负责。
    """
    early_v2_config = {
        "version": 2,
        "trash_weapon_ids": ["weapon_v2"],
        "treasure_essence_stats": [
            {"attribute": "atk", "secondary": None, "skill": "fire"}
        ],
        "treasure_action": "lock",
        "trash_action": "unlock",
        "high_level_treasure_enabled": False,
        "high_level_treasure_attribute_threshold": 3,
        "high_level_treasure_secondary_threshold": 3,
        "high_level_treasure_skill_threshold": 3,
        # 早期 v2 没有 non_five_star_behavior 和 auto_page_flip
    }

    migrated = UserSetting.migrate_from_old_version(early_v2_config)

    # 验证迁移链完整性
    assert migrated.version == UserSetting._VERSION

    # 验证旧数据保留
    assert migrated.trash_weapon_ids == ["weapon_v2"]
    assert len(migrated.treasure_essence_stats) == 1
    assert migrated.treasure_essence_stats[0].attribute == "atk"

    # 验证关键字段的默认值（只验证几个代表性字段）
    assert migrated.non_five_star_behavior == "process"
    assert migrated.auto_page_flip is True
    assert migrated.fix_grid_row_offset_after_page_flip is True
    assert migrated.fix_page_flip_overscroll is False
    assert migrated.update_mirror == "github"
    assert migrated.update_flow == "github"
    assert migrated.treasure_essence_match_mode == "all"


def test_migrations_completeness():
    """测试 _MIGRATIONS 字典完整性，确保所有中间版本都有迁移函数"""
    current_version = UserSetting._VERSION
    migrations = UserSetting._MIGRATIONS

    # 检查从版本 2 到当前版本的所有迁移路径
    for v in range(2, current_version):
        assert v in migrations, (
            f"缺少迁移函数：v{v} → v{v + 1}\n"
            f"请在 UserSetting 中添加 _migrate_v{v}_to_v{v + 1} 方法"
        )


def test_migration_sets_all_required_fields():
    """测试迁移函数是否为所有新增字段设置了默认值

    从最旧版本（v2）迁移到当前版本后，所有字段都应该有值。
    这个测试确保迁移函数不会遗漏任何字段。

    注意：由于 Pydantic 模型有默认值，即使迁移函数没有设置字段，
    模型也会使用默认值。所以这个测试检查的是迁移后的字典是否包含所有字段，
    而不是检查字段的值。

    - v1→v2: 基础字段（trash_weapon_ids, treasure_essence_stats, treasure_action, trash_action, high_level_treasure_*）
    """
    # 最简化的 v2 配置（只有必需字段）
    minimal_v2_config = {
        "version": 2,
        "trash_weapon_ids": [],
        "treasure_essence_stats": [],
        "treasure_action": "lock",
        "trash_action": "unlock",
        "high_level_treasure_enabled": False,
        "high_level_treasure_attribute_threshold": 3,
        "high_level_treasure_secondary_threshold": 3,
        "high_level_treasure_skill_threshold": 3,
    }

    # 先手动执行迁移函数，检查迁移后的字典
    from copy import deepcopy

    migrated_data = deepcopy(minimal_v2_config)

    # 执行所有迁移函数
    for version in range(2, UserSetting._VERSION):
        migration_func = UserSetting._MIGRATIONS.get(version)
        if migration_func:
            migration_func(migrated_data)

    # 检查迁移后的字典是否包含所有期望的字段
    expected_fields = set(UserSetting.model_fields.keys())
    actual_fields = set(migrated_data.keys())

    # 排除 version 字段，因为它在迁移过程中会被更新
    expected_fields.discard("version")
    actual_fields.discard("version")

    missing_fields = expected_fields - actual_fields
    assert not missing_fields, (
        f"迁移函数遗漏了以下字段: {missing_fields}\n"
        f"请在相应的迁移函数中添加 data.setdefault() 调用"
    )

    # 验证迁移后的配置可以正确解析
    migrated = UserSetting.migrate_from_old_version(minimal_v2_config)

    # 验证关键字段的默认值
    assert migrated.version == UserSetting._VERSION

    # v2→v3 补充的字段
    assert migrated.non_five_star_behavior == "process"
    assert migrated.auto_page_flip is True

    # v3→v4 补充的字段
    assert migrated.update_mirror == "github"
    assert migrated.update_proxy == ""

    # v4→v5 补充的字段（Mirror 酱配置）
    assert migrated.update_mirrorchyan_res_id == ""
    assert migrated.update_mirrorchyan_cdk == ""
    assert migrated.update_mirrorchyan_user_agent == "EER_APP"
    assert migrated.update_flow == "github"
    assert migrated.update_github_mirror == "github"

    # v5→v6 补充的字段（宝藏基质匹配和同类型限制）
    assert migrated.treasure_essence_match_mode == "all"
    assert migrated.high_level_treasure_match_mode == "any"
    assert migrated.high_level_treasure_sum_threshold == 6
    assert migrated.high_level_treasure_only_check_attribute is True
    assert migrated.high_level_treasure_only_check_secondary is True
    assert migrated.high_level_treasure_only_check_skill is True
    assert migrated.same_type_treasure_limit_enabled is True
    assert migrated.same_type_treasure_limit == 1
    assert migrated.same_type_group_mode == "by_weapon"
    assert migrated.same_type_keep_best is True
    assert migrated.fix_grid_row_offset_after_page_flip is True
    assert migrated.fix_page_flip_overscroll is False

    # v5→v6 补充的字段（非无瑕基质专用的高等级判定设置）
    assert migrated.non_five_star_separate_high_level_settings is False
    assert migrated.non_five_star_high_level_attribute_threshold == 3
    assert migrated.non_five_star_high_level_secondary_threshold == 3
    assert migrated.non_five_star_high_level_skill_threshold == 3
    assert migrated.non_five_star_high_level_match_mode == "any"
    assert migrated.non_five_star_high_level_sum_threshold == 6
    assert migrated.non_five_star_high_level_only_check_attribute is True
    assert migrated.non_five_star_high_level_only_check_secondary is True
    assert migrated.non_five_star_high_level_only_check_skill is True

    # v6→v7 补充的字段（留大弃小等级比较方式）
    assert migrated.same_type_keep_best_mode == "sum"

    # v8→v9 补充的字段（冗余清理，默认关闭）
    assert migrated.redundant_cleanup_enabled is False
    assert migrated.redundant_cleanup_trigger == "scan_complete"
    assert migrated.redundant_action == "deprecate"


def test_migrate_v8_to_v9_adds_redundant_cleanup_fields():
    """v8 → v9: 补充冗余清理字段，默认关闭，已有字段保留。"""
    v8_config = {
        "version": 8,
        "trash_weapon_ids": ["w1"],
        "same_type_treasure_limit_enabled": True,
        "same_type_treasure_limit": 2,
    }

    migrated = UserSetting.migrate_from_old_version(v8_config)

    assert migrated.version == UserSetting._VERSION
    assert migrated.trash_weapon_ids == ["w1"]
    assert migrated.same_type_treasure_limit == 2
    assert migrated.redundant_cleanup_enabled is False
    assert migrated.redundant_cleanup_trigger == "scan_complete"
    assert migrated.redundant_action == "deprecate"


def test_legacy_cn_update_mirror_normalizes_to_yituliu_flow():
    setting = UserSetting.model_validate(
        {
            "version": UserSetting._VERSION,
            "update_mirror": "cn",
        }
    )

    assert setting.update_flow == "cn_yituliu"
    assert setting.update_mirror == "github"
    assert setting.update_github_mirror == "github"


def test_frontend_config_version_matches_backend():
    """确保前端 settings.vue 中的 config version 与后端 UserSetting._VERSION 一致。

    前端发送的 version 字段必须和后端校验的版本号匹配，否则配置将无法保存。
    如果此测试失败，请同步更新 frontend/src/pages/settings.vue 中的 version 值。
    """
    import re
    from pathlib import Path

    settings_vue = (
        Path(__file__).resolve().parent.parent
        / "frontend"
        / "src"
        / "pages"
        / "settings.vue"
    )
    assert settings_vue.exists(), f"找不到前端设置页面: {settings_vue}"

    content = settings_vue.read_text(encoding="utf-8")

    # 从 config computed 中提取 version: <number>
    # 匹配 return { version: N, ... } 内的 version 字段
    match = re.search(r"return\s*\{[^}]*version:\s*(\d+)", content)
    assert match, (
        "无法从 settings.vue 的 config computed 中提取 version 字段，"
        "请检查模板格式是否变更"
    )

    frontend_version = int(match.group(1))
    backend_version = UserSetting._VERSION

    assert frontend_version == backend_version, (
        f"前后端配置版本不一致！前端 version={frontend_version}，后端 _VERSION={backend_version}\n"
        f"请将 frontend/src/pages/settings.vue 中的 version 改为 {backend_version}，"
        f"或更新 UserSetting._VERSION 以匹配前端。"
    )
