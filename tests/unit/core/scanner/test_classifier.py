"""Tests for Layer 1: classifier.py — pure classification logic."""

from unittest.mock import MagicMock

import pytest

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
    RarityLabel,
)
from endfield_essence_recognizer.core.scanner.classifier import classify_essence
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
)
from endfield_essence_recognizer.game_data.models.v2 import EssenceStatV2, StatType
from endfield_essence_recognizer.schemas.user_setting import (
    EssenceStats,
    NonFiveStarBehavior,
    UserSetting,
)


def _make_stat(stat_id: str, stat_type: StatType) -> EssenceStatV2:
    return EssenceStatV2(stat_id=stat_id, name=stat_id, type=stat_type)


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


def test_classify_trash_no_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """无匹配武器且无自定义规则 → TRASH。"""
    result = classify_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TRASH
    assert result.matched_weapon_ids == set()
    assert result.is_high_level is False


def test_classify_treasure_custom_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """匹配自定义宝藏基质 → TREASURE。"""
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]
    result = classify_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert result.custom_treasure_name is not None  # 有自定义基质名称


def test_classify_treasure_weapon_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """匹配武器 → TREASURE。"""
    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_001"]
    result = classify_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.quality == EssenceQuality.TREASURE
    assert "wpn_001" in result.matched_weapon_ids


def test_classify_treasure_all_blocked(
    mock_static_game_data, default_settings, default_essence_data
):
    """所有匹配武器被拦截 + 高等级 → TREASURE（all_blocked=True）。"""
    default_settings.treasure_essence_stats = [
        EssenceStats(attribute="A", secondary="B", skill="C")
    ]
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_attribute_threshold = 1
    default_settings.high_level_treasure_secondary_threshold = 1
    default_settings.high_level_treasure_skill_threshold = 1
    essence = EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[6, 6, 3],
        rarity=RarityLabel.FIVE,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )
    result = classify_essence(essence, default_settings, mock_static_game_data)
    assert result.quality == EssenceQuality.TREASURE
    assert result.is_high_level is True


def test_classify_skip_non_five_star(
    mock_static_game_data, default_settings, default_essence_data
):
    """非无瑕基质 + SKIP 行为 → SKIP。"""
    default_settings.non_five_star_behavior = NonFiveStarBehavior.SKIP
    essence = EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[0, 0, 0],
        rarity=RarityLabel.OTHER,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )
    result = classify_essence(essence, default_settings, mock_static_game_data)
    assert result.quality == EssenceQuality.SKIP


def test_classify_skip_stop(mock_static_game_data, default_settings):
    """非无瑕基质 + STOP 行为 → SKIP + stop_scan=True。"""
    default_settings.non_five_star_behavior = NonFiveStarBehavior.STOP
    essence = EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[0, 0, 0],
        rarity=RarityLabel.OTHER,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )
    result = classify_essence(essence, default_settings, mock_static_game_data)
    assert result.quality == EssenceQuality.SKIP
    assert result.stop_scan is True


def test_classify_high_level_treasure(mock_static_game_data, default_settings):
    """五无瑕基质 + 高等级属性 → TREASURE + is_high_level=True。"""
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_attribute_threshold = 5
    essence = EssenceData(
        stats=["A", "B", "C"],
        stat_types=[StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL],
        levels=[6, 6, 3],
        rarity=RarityLabel.FIVE,
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )
    result = classify_essence(essence, default_settings, mock_static_game_data)
    assert result.quality == EssenceQuality.TREASURE
    assert result.is_high_level is True
    assert "高等级" in result.high_level_info
