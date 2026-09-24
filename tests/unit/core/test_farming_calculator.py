"""刷取计算器的测试。"""

import pytest

from endfield_essence_recognizer.core.farming_calculator import (
    compute_farming_recommendation,
)


def test_compute_farming_recommendation_basic():
    """测试基本的刷取建议计算。"""
    result = compute_farming_recommendation(
        weapon_id="wpn_test",
        weapon_name="Test Weapon",
        current_levels=(1, 1, 1),
        target_levels=(6, 6, 3),
    )
    assert result.weapon_id == "wpn_test"
    assert result.weapon_name == "Test Weapon"
    assert result.current_levels == (1, 1, 1)
    assert result.target_levels == (6, 6, 3)
    assert len(result.affix_results) == 3
    assert result.total_expected_runs > 0


def test_compute_farming_recommendation_no_upgrade():
    """测试当前等级等于目标等级时（无需升级）。"""
    result = compute_farming_recommendation(
        weapon_id="wpn_test",
        weapon_name="Test Weapon",
        current_levels=(6, 6, 3),
        target_levels=(6, 6, 3),
    )
    assert result.total_expected_essences == 0
    assert result.total_expected_runs == 0


def test_compute_farming_recommendation_partial():
    """测试部分升级（某些词条已达到目标）。"""
    result = compute_farming_recommendation(
        weapon_id="wpn_test",
        weapon_name="Test Weapon",
        current_levels=(5, 6, 3),
        target_levels=(6, 6, 3),
    )
    assert result.affix_results[0].expected_attempts > 0
    assert result.affix_results[1].expected_attempts == 0
    assert result.affix_results[2].expected_attempts == 0


def test_compute_farming_recommendation_invalid_current_levels():
    """测试无效的当前等级会抛出 ValueError。"""
    with pytest.raises(ValueError, match="Invalid current_levels"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(0, 1, 1),
            target_levels=(6, 6, 3),
        )
    with pytest.raises(ValueError, match="Invalid current_levels"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(7, 1, 1),
            target_levels=(6, 6, 3),
        )
    with pytest.raises(ValueError, match="Invalid current_levels"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(1, 1, 4),
            target_levels=(6, 6, 3),
        )


def test_compute_farming_recommendation_invalid_target_levels():
    """测试无效的目标等级会抛出 ValueError。"""
    with pytest.raises(ValueError, match="Invalid target_levels"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(1, 1, 1),
            target_levels=(0, 6, 3),
        )
    with pytest.raises(ValueError, match="Invalid target_levels"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(1, 1, 1),
            target_levels=(6, 7, 3),
        )


def test_compute_farming_recommendation_current_exceeds_target():
    """测试当前等级大于目标等级会抛出 ValueError。"""
    with pytest.raises(ValueError, match="must not exceed"):
        compute_farming_recommendation(
            weapon_id="wpn_test",
            weapon_name="Test Weapon",
            current_levels=(6, 1, 1),
            target_levels=(5, 6, 3),
        )
