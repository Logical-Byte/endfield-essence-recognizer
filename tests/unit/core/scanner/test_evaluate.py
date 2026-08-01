from unittest.mock import MagicMock

import pytest

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
    RarityLabel,
)
from endfield_essence_recognizer.core.scanner.evaluate import evaluate_essence
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
)
from endfield_essence_recognizer.game_data.models.v2 import EssenceStatV2, StatType
from endfield_essence_recognizer.schemas.user_setting import (
    EssenceStats,
    NonFiveStarBehavior,
    TreasureMatchMode,
    UserSetting,
)


def _make_stat(stat_id: str, stat_type: StatType) -> EssenceStatV2:
    """Create a mock EssenceStatV2 with the given type."""
    return EssenceStatV2(stat_id=stat_id, name=stat_id, type=stat_type)


# 预定义测试用的 stat 对象
_STAT_A = _make_stat("A", StatType.ATTRIBUTE)
_STAT_B = _make_stat("B", StatType.SECONDARY)
_STAT_C = _make_stat("C", StatType.SKILL)

_MOCK_STAT_TABLE: dict[str, EssenceStatV2] = {
    "A": _STAT_A,
    "B": _STAT_B,
    "C": _STAT_C,
}


@pytest.fixture
def mock_static_game_data():
    mock_data = MagicMock()

    # 按 stat_id 返回对应的 EssenceStatV2（含类型信息）
    mock_data.get_stat.side_effect = lambda sid: _MOCK_STAT_TABLE.get(sid)
    mock_data.find_weapons_by_stats.return_value = []
    mock_data.get_weapon.return_value = None
    mock_data.get_weapon_type.return_value = None

    return mock_data


@pytest.fixture
def default_settings():
    return UserSetting()


@pytest.fixture
def default_essence_data():
    return EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[0, 0, 0],
        rarity=RarityLabel.OTHER,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )


def test_evaluate_trash(mock_static_game_data, default_settings, default_essence_data):
    """
    Test that an essence matching no rules and no weapons is evaluated as TRASH.

    Condition:
    - Tables are empty (no known weapons).
    - No custom rules.
    - No high level logic enabled.
    """
    # Setup nothing in tables -> Trash
    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message


def test_evaluate_treasure_custom(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a user-defined custom treasure rule is evaluated as TREASURE.

    Condition:
    - User setting has a custom treasure rule matching the stats (A, B, C).
    """
    # Setup custom treasure rule
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert "宝藏" in result.log_message
    assert "自定义基质" in result.log_message


def test_evaluate_custom_treasure_match_mode_any(
    mock_static_game_data, default_settings, default_essence_data
):
    """任一已设置槽位匹配即可视为自定义宝藏。"""
    default_settings.treasure_essence_match_mode = TreasureMatchMode.ANY
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary=None, skill=None)
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TREASURE


def test_evaluate_custom_treasure_match_mode_only_checks_configured_slots(
    mock_static_game_data, default_settings, default_essence_data
):
    """仅模式只检查用户设置的槽位，未设置槽位会被忽略。"""
    default_settings.treasure_essence_match_mode = TreasureMatchMode.ONLY
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill=None)
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TREASURE


def test_evaluate_custom_treasure_match_mode_only_rejects_configured_mismatch(
    mock_static_game_data, default_settings, default_essence_data
):
    """仅模式要求所有已设置槽位都匹配。"""
    default_settings.treasure_essence_match_mode = TreasureMatchMode.ONLY
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="X", skill=None)
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TRASH


def test_evaluate_custom_treasure_match_mode_all_requires_three_slots(
    mock_static_game_data, default_settings, default_essence_data
):
    """和模式要求 1、2、3 三个槽位都设置且匹配。"""
    default_settings.treasure_essence_match_mode = TreasureMatchMode.ALL
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill=None)
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TRASH


def test_evaluate_custom_treasure_match_mode_all_matches_three_slots(
    mock_static_game_data, default_settings, default_essence_data
):
    """和模式下 1、2、3 三个槽位全部匹配时视为宝藏。"""
    default_settings.treasure_essence_match_mode = TreasureMatchMode.ALL
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TREASURE


def test_evaluate_treasure_weapon_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a known weapon is evaluated as TREASURE.
    """
    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_test"]
    weapon_mock = MagicMock()
    weapon_mock.weapon_id = "wpn_test"
    weapon_mock.name = "TestWeapon"
    weapon_mock.rarity = 6
    weapon_mock.weapon_type = 1
    mock_static_game_data.get_weapon.return_value = weapon_mock
    weapon_type_mock = MagicMock()
    weapon_type_mock.name = "TestType"
    mock_static_game_data.get_weapon_type.return_value = weapon_type_mock

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert "TestWeapon" in result.log_message
    assert "TestType" in result.log_message
    assert "wpn_test" in result.matched_weapons


def test_evaluate_weapon_match_trash_filter(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a known weapon is evaluated as TRASH if that weapon is filtered.
    """
    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_test"]
    weapon_mock = MagicMock()
    weapon_mock.weapon_id = "wpn_test"
    weapon_mock.name = "TestWeapon"
    weapon_mock.rarity = 6
    weapon_mock.weapon_type = "TestType"
    mock_static_game_data.get_weapon.return_value = weapon_mock
    weapon_type_mock = MagicMock()
    weapon_type_mock.name = "TestType"
    mock_static_game_data.get_weapon_type.return_value = weapon_type_mock

    # Filter it out
    default_settings.trash_weapon_ids = ["wpn_test"]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TRASH
    assert "手动拦截" in result.log_message
    assert "wpn_test" in result.matched_weapons


def test_evaluate_high_level(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test high-level attribute evaluation.
    """
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_attribute_threshold = 10

    stat = MagicMock()
    stat.stat_id = "A"
    stat.name = "AttrA"
    stat.type = "ATTRIBUTE"
    mock_static_game_data.get_stat.side_effect = None
    mock_static_game_data.get_stat.return_value = stat

    # Level 11 >= Threshold 10
    default_essence_data.levels = [11, 0, 0]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.is_high_level is True
    assert "AttrA+11" in result.log_message


def test_evaluate_high_level_only_mode_with_category_toggles(
    mock_static_game_data, default_settings, default_essence_data
):
    """仅模式下，只有勾选的类别会被检查。"""
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_match_mode = TreasureMatchMode.ONLY
    default_settings.high_level_treasure_attribute_threshold = 3
    default_settings.high_level_treasure_secondary_threshold = 3
    default_settings.high_level_treasure_skill_threshold = 3
    # Only check attribute
    default_settings.high_level_treasure_only_check_attribute = True
    default_settings.high_level_treasure_only_check_secondary = False
    default_settings.high_level_treasure_only_check_skill = False
    # Attribute level meets threshold, others don't
    default_essence_data.levels = [3, 0, 0]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert result.is_high_level is True


def test_evaluate_high_level_only_mode_unchecked_category_ignored(
    mock_static_game_data, default_settings, default_essence_data
):
    """仅模式下，未勾选的类别即使不达标也不影响判定。"""
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_match_mode = TreasureMatchMode.ONLY
    default_settings.high_level_treasure_attribute_threshold = 3
    default_settings.high_level_treasure_secondary_threshold = 5
    default_settings.high_level_treasure_skill_threshold = 3
    # Check attribute and skill, skip secondary
    default_settings.high_level_treasure_only_check_attribute = True
    default_settings.high_level_treasure_only_check_secondary = False
    default_settings.high_level_treasure_only_check_skill = True
    # Attribute=3 (meets), Secondary=0 (doesn't meet but unchecked), Skill=2 (doesn't meet)
    default_essence_data.levels = [3, 0, 2]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    # Skill doesn't meet threshold so should be TRASH
    assert result.quality == EssenceQuality.TRASH


def test_evaluate_high_level_only_mode_all_categories_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """仅模式下，所有勾选类别都达标时视为宝藏。"""
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_match_mode = TreasureMatchMode.ONLY
    default_settings.high_level_treasure_attribute_threshold = 3
    default_settings.high_level_treasure_secondary_threshold = 3
    default_settings.high_level_treasure_skill_threshold = 2
    default_settings.high_level_treasure_only_check_attribute = True
    default_settings.high_level_treasure_only_check_secondary = True
    default_settings.high_level_treasure_only_check_skill = True
    default_essence_data.levels = [3, 3, 2]

    stat = MagicMock()
    stat.name = "AttrA"
    mock_static_game_data.get_stat.return_value = stat

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert result.is_high_level is True


def test_evaluate_high_level_all_mode_requires_all_slots(
    mock_static_game_data, default_settings, default_essence_data
):
    """高等级和模式要求 1、2、3 三个槽位都满足阈值。"""
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_match_mode = TreasureMatchMode.ALL
    default_settings.high_level_treasure_attribute_threshold = 3
    default_settings.high_level_treasure_secondary_threshold = 3
    default_settings.high_level_treasure_skill_threshold = 3
    # Only attribute meets threshold
    default_essence_data.levels = [3, 0, 0]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TRASH


def test_evaluate_same_type_treasure_limit_marks_later_items_as_trash(
    mock_static_game_data, default_settings, default_essence_data
):
    """同类型宝藏达到上限后，后续同属性组合会视为养成材料。"""
    default_settings.same_type_treasure_limit_enabled = True
    default_settings.same_type_treasure_limit = 1
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]

    first = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    second = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert first.quality == EssenceQuality.TREASURE
    assert second.quality == EssenceQuality.TRASH
    assert "达到设置上限" in second.log_message


def test_evaluate_same_type_treasure_limit_disabled_updates_best_levels(
    mock_static_game_data, default_settings, default_essence_data
):
    """限制关闭时，仍会更新 _same_type_best_levels 和 _same_type_treasure_counts。"""
    default_settings.same_type_treasure_limit_enabled = False
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]

    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_A", "wpn_B"]
    weapon_mock = MagicMock()
    weapon_mock.weapon_id = "wpn_A"
    weapon_mock.name = "WeaponA"
    weapon_mock.rarity = 6
    weapon_mock.weapon_type = 1
    mock_static_game_data.get_weapon.return_value = weapon_mock

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )

    assert result.quality == EssenceQuality.TREASURE
    # _same_type_best_levels 应包含两把武器，等级均为 (1, 1, 1)（levels=[0,0,0] 或 1）
    assert "wpn_A" in default_settings._same_type_best_levels
    assert "wpn_B" in default_settings._same_type_best_levels
    assert default_settings._same_type_best_levels["wpn_A"] == (1, 1, 1)
    assert default_settings._same_type_best_levels["wpn_B"] == (1, 1, 1)
    # _same_type_treasure_counts 应累计 1
    assert default_settings._same_type_treasure_counts["wpn_A"] == 1
    assert default_settings._same_type_treasure_counts["wpn_B"] == 1


def test_evaluate_same_type_treasure_limit_disabled_keeps_highest_level(
    mock_static_game_data, default_settings, default_essence_data
):
    """限制关闭时，同一武器的多次扫描应保留最高等级。"""
    default_settings.same_type_treasure_limit_enabled = False
    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_A"]
    weapon_mock = MagicMock()
    weapon_mock.weapon_id = "wpn_A"
    weapon_mock.name = "WeaponA"
    weapon_mock.rarity = 6
    weapon_mock.weapon_type = 1
    mock_static_game_data.get_weapon.return_value = weapon_mock

    # 第一次扫描：低等级
    default_essence_data.levels = [1, 1, 1]
    evaluate_essence(default_essence_data, default_settings, mock_static_game_data)
    assert default_settings._same_type_best_levels["wpn_A"] == (1, 1, 1)

    # 第二次扫描：更高等级
    default_essence_data.levels = [3, 2, 1]
    evaluate_essence(default_essence_data, default_settings, mock_static_game_data)
    assert default_settings._same_type_best_levels["wpn_A"] == (3, 2, 1)

    # 第三次扫描：更低等级，不应覆盖
    default_essence_data.levels = [2, 1, 1]
    evaluate_essence(default_essence_data, default_settings, mock_static_game_data)
    assert default_settings._same_type_best_levels["wpn_A"] == (3, 2, 1)

    # 计数应累计 3 次
    assert default_settings._same_type_treasure_counts["wpn_A"] == 3


def test_evaluate_non_five_star_skip(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test skipping non-5-star essence.
    """
    default_essence_data.rarity = RarityLabel.FOUR
    default_settings.non_five_star_behavior = NonFiveStarBehavior.SKIP

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.SKIP
    assert "跳过" in result.log_message
    assert result.stop_scan is False


def test_evaluate_non_five_star_stop(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test stopping scan when non-5-star essence is encountered.
    """
    default_essence_data.rarity = RarityLabel.FOUR
    default_settings.non_five_star_behavior = NonFiveStarBehavior.STOP

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.SKIP
    assert result.stop_scan is True
    assert "结束本次扫描" in result.log_message


def test_evaluate_non_five_star_process(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test processing non-5-star essence as normal.
    """
    default_essence_data.rarity = RarityLabel.FOUR
    default_settings.non_five_star_behavior = NonFiveStarBehavior.PROCESS

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    # Should fall through to normal evaluation (Trash in this blank case)
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message
