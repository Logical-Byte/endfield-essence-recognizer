"""Tests for Layer 3: log_builder.py — log message assembly."""

from unittest.mock import MagicMock

import pytest

from endfield_essence_recognizer.core.scanner.log_builder import build_evaluation_result
from endfield_essence_recognizer.core.scanner.models import (
    ClaimResult,
    ClassificationResult,
    EssenceQuality,
    RejectReason,
)
from endfield_essence_recognizer.schemas.user_setting import UserSetting


@pytest.fixture
def mock_static_game_data():
    mock_data = MagicMock()
    mock_data.get_weapon.return_value = None
    mock_data.get_weapon_type.return_value = None
    mock_data.get_rarity_color.return_value = "#FFFFFF"
    return mock_data


@pytest.fixture
def default_settings():
    return UserSetting()


def test_skip_log(mock_static_game_data, default_settings):
    """SKIP 基质的日志消息。"""
    classification = ClassificationResult(quality=EssenceQuality.SKIP)
    result = build_evaluation_result(
        classification, ClaimResult(), mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.SKIP
    assert "非无瑕基质" in result.log_message


def test_skip_stop_log(mock_static_game_data, default_settings):
    """SKIP + stop_scan 的日志消息。"""
    classification = ClassificationResult(quality=EssenceQuality.SKIP, stop_scan=True)
    result = build_evaluation_result(
        classification, ClaimResult(), mock_static_game_data, default_settings
    )
    assert result.stop_scan is True
    assert "结束本次扫描" in result.log_message


def test_trash_no_match_log(mock_static_game_data, default_settings):
    """无匹配武器的 TRASH 日志消息。"""
    classification = ClassificationResult(quality=EssenceQuality.TRASH)
    result = build_evaluation_result(
        classification, ClaimResult(), mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message
    assert "不匹配任何已实装武器" in result.log_message


def test_treasure_weapon_match_log(mock_static_game_data, default_settings):
    """匹配武器的宝藏日志消息。"""
    mock_weapon = MagicMock()
    mock_weapon.name = "测试武器"
    mock_weapon.rarity = 5
    mock_weapon.weapon_type = "sword"
    mock_static_game_data.get_weapon.return_value = mock_weapon

    classification = ClassificationResult(
        quality=EssenceQuality.TREASURE,
        matched_weapon_ids={"wpn_001"},
        is_high_level=False,
    )
    result = build_evaluation_result(
        classification, ClaimResult(), mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.TREASURE
    assert "宝藏" in result.log_message
    assert "测试武器" in result.log_message


def test_rejected_by_limit_log(mock_static_game_data, default_settings):
    """达到数量上限的拒绝日志消息。"""
    default_settings.same_type_treasure_limit = 2
    classification = ClassificationResult(
        quality=EssenceQuality.TREASURE,
        matched_weapon_ids={"wpn_001"},
    )
    claim_result = ClaimResult(reject_reason=RejectReason.LIMIT)
    result = build_evaluation_result(
        classification, claim_result, mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message
    assert "达到设置上限" in result.log_message


def test_rejected_by_worse_level_log(mock_static_game_data, default_settings):
    """等级劣于已保存最佳的拒绝日志消息。"""
    classification = ClassificationResult(
        quality=EssenceQuality.TREASURE,
        matched_weapon_ids={"wpn_001"},
    )
    claim_result = ClaimResult(reject_reason=RejectReason.WORSE_LEVEL)
    result = build_evaluation_result(
        classification, claim_result, mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message
    assert "等级低于已保存" in result.log_message


def test_rejected_by_non_downgrade_log(mock_static_game_data, default_settings):
    """非降级原则过滤的拒绝日志消息。"""
    classification = ClassificationResult(
        quality=EssenceQuality.TREASURE,
        matched_weapon_ids={"wpn_001"},
    )
    claim_result = ClaimResult(reject_reason=RejectReason.NON_DOWNGRADE)
    result = build_evaluation_result(
        classification, claim_result, mock_static_game_data, default_settings
    )
    assert result.quality == EssenceQuality.TRASH
    assert "养成材料" in result.log_message
    assert "非降级原则" in result.log_message
