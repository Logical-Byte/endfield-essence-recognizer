from unittest.mock import MagicMock, patch

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
from endfield_essence_recognizer.schemas.user_setting import EssenceStats, UserSetting


@pytest.fixture
def mock_static_game_data():
    with patch("endfield_essence_recognizer.dependencies.get_static_game_data") as m:
        mock_data = MagicMock()
        m.return_value = mock_data

        # Default behaviors
        mock_data.get_gem.return_value = None
        mock_data.find_weapons_by_stats.return_value = []
        mock_data.get_weapon.return_value = None
        mock_data.get_weapon_type.return_value = None

        yield mock_data


@pytest.fixture
def default_settings():
    return UserSetting()


@pytest.fixture
def default_essence_data():
    return EssenceData(
        stats=["A", "B", "C"],
        levels=[0, 0, 0],
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
    assert "符合你设定的宝藏基质条件" in result.log_message


def test_evaluate_treasure_weapon_match(
    mock_static_game_data, default_settings, default_essence_data
):
    """
    Test that an essence matching a known weapon is evaluated as TREASURE.
    """
    mock_static_game_data.find_weapons_by_stats.return_value = ["wpn_test"]
    mock_static_game_data.get_weapon.return_value = MagicMock(
        weapon_id="wpn_test", name="TestWeapon", rarity=6, weapon_type=1
    )
    mock_static_game_data.get_weapon_type.return_value = MagicMock(name="TestType")

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
    mock_static_game_data.get_weapon.return_value = MagicMock(
        weapon_id="wpn_test", name="TestWeapon", rarity=6, weapon_type=1
    )
    mock_static_game_data.get_weapon_type.return_value = MagicMock(name="TestType")

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

    gem = MagicMock()
    gem.gem_id = "A"
    gem.name = "AttrA"
    gem.type = "ATTRIBUTE"
    mock_static_game_data.get_gem.return_value = gem

    # Level 11 >= Threshold 10
    default_essence_data.levels = [11, 0, 0]

    result = evaluate_essence(
        default_essence_data, default_settings, mock_static_game_data
    )
    assert result.is_high_level is True
    assert "AttrA+11" in result.log_message
    assert "宝藏" in result.log_message
