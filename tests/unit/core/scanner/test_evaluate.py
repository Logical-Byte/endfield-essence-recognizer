from unittest.mock import patch

import pytest

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)
from endfield_essence_recognizer.core.scanner.evaluate import evaluate_essence
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
)
from endfield_essence_recognizer.models.user_setting import EssenceStats, UserSetting


@pytest.fixture
def mock_game_data():
    with (
        patch("endfield_essence_recognizer.game_data.gem_table", new={}) as m_gem,
        patch(
            "endfield_essence_recognizer.game_data.weapon_basic_table", new={}
        ) as m_weapon_basic,
        patch(
            "endfield_essence_recognizer.game_data.weapon.weapon_stats_dict", new={}
        ) as m_weapon_stats,
        patch(
            "endfield_essence_recognizer.game_data.get_translation",
            return_value="TestType",
        ),
        patch(
            "endfield_essence_recognizer.game_data.item.get_item_name",
            return_value="TestWeapon",
        ),
        patch(
            "endfield_essence_recognizer.game_data.weapon.get_gem_tag_name",
            return_value="TestAttr",
        ),
        patch(
            "endfield_essence_recognizer.game_data.weapon.weapon_type_int_to_translation_key",
            return_value="test.key",
        ),
    ):
        yield {
            "gem_table": m_gem,
            "weapon_basic_table": m_weapon_basic,
            "weapon_stats_dict": m_weapon_stats,
        }


@pytest.fixture
def default_settings():
    return UserSetting(
        # Defaults
    )


@pytest.fixture
def default_essence_data():
    return EssenceData(
        stats=["A", "B", "C"],
        levels=[0, 0, 0],
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )


def test_evaluate_trash(mock_game_data, default_settings, default_essence_data):
    """
    Test that an essence matching no rules and no weapons is evaluated as TRASH.

    Condition:
    - Tables are empty (no known weapons).
    - No custom rules.
    - No high level logic enabled.
    """
    # Setup nothing in tables -> Trash
    result = evaluate_essence(default_essence_data, default_settings)
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message


def test_evaluate_treasure_custom(
    mock_game_data, default_settings, default_essence_data
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

    result = evaluate_essence(default_essence_data, default_settings)
    assert result.quality == EssenceQuality.TREASURE
    assert "宝藏" in result.log_message
    assert "符合你设定的宝藏基质条件" in result.log_message


def test_evaluate_weapon_match_treasure(
    mock_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a known weapon's stats is evaluated as TREASURE.

    Condition:
    - Game data contains 'weapon_1' with stats matching the essence.
    - 'weapon_1' is NOT in the user's trash filter list.
    """
    # Setup weapon dict
    mock_game_data["weapon_stats_dict"]["weapon_1"] = {
        "attribute": "A",
        "secondary": "B",
        "skill": "C",
    }
    # Setup basic info for rarity
    mock_game_data["weapon_basic_table"]["weapon_1"] = {"rarity": 5}

    result = evaluate_essence(default_essence_data, default_settings)
    assert result.quality == EssenceQuality.TREASURE
    assert "TestWeapon" in result.log_message
    assert "weapon_1" in result.matched_weapons


def test_evaluate_weapon_match_trash_filter(
    mock_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a known weapon is evaluated as TRASH if that weapon is filtered.

    Condition:
    - Game data matches 'weapon_1'.
    - User setting 'trash_weapon_ids' includes 'weapon_1'.
    """
    # Setup weapon dict
    mock_game_data["weapon_stats_dict"]["weapon_1"] = {
        "attribute": "A",
        "secondary": "B",
        "skill": "C",
    }
    mock_game_data["weapon_basic_table"]["weapon_1"] = {"rarity": 5}

    # Filter it out
    default_settings.trash_weapon_ids = ["weapon_1"]

    result = evaluate_essence(default_essence_data, default_settings)
    assert result.quality == EssenceQuality.TRASH
    assert "手动拦截" in result.log_message
    assert "weapon_1" in result.matched_weapons


def test_evaluate_high_level_attribute(
    mock_game_data, default_settings, default_essence_data
):
    """
    Test that an essence with high-level stats is evaluated as TREASURE (High Level).

    Condition:
    - 'high_level_treasure_enabled' is True.
    - One attribute level meets or exceeds the threshold.
    """
    # Setup high level checks
    default_settings.high_level_treasure_enabled = True
    default_settings.high_level_treasure_attribute_threshold = 10

    # Mock gem table to identify stat type 0 (attribute)
    # termType: 0=base, 1=secondary, 2=skill
    mock_game_data["gem_table"]["A"] = {"termType": 0}

    default_essence_data.levels = [10, 0, 0]

    result = evaluate_essence(default_essence_data, default_settings)
    assert result.quality == EssenceQuality.TREASURE
    assert result.is_high_level
    assert "含高等级属性词条" in result.log_message
