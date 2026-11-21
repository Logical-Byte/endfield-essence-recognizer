"""自定义能量淤积点模型校验的测试。"""

import pytest
from pydantic import ValidationError

from endfield_essence_recognizer.schemas.custom_alluvium import (
    MAX_STAT_POOL_SIZE,
    CustomAlluvium,
)


def test_duplicate_stats_are_deduped_in_place():
    """重复词条会被去重并保持原顺序。

    重复项不只是冗余：附加/技能属性重复会让规划器对同一属性重复生成方案，
    基础属性去重后不足三项还会从「按勾选池计算」退化成「不限制」。
    """
    entry = CustomAlluvium(
        name="带重复",
        attribute_stats=[
            "gat_passive_attr_agi",
            "gat_passive_attr_main",
            "gat_passive_attr_agi",
        ],
        secondary_stats=["gat_passive_attr_atk", "gat_passive_attr_atk"],
        skill_stats=["gst_passive_force", "gst_passive_heal", "gst_passive_force"],
    )

    assert entry.attribute_stats == ["gat_passive_attr_agi", "gat_passive_attr_main"]
    assert entry.secondary_stats == ["gat_passive_attr_atk"]
    assert entry.skill_stats == ["gst_passive_force", "gst_passive_heal"]


def test_stat_pool_size_is_capped():
    """单组词条超过上限时拒绝，避免超长池让规划器的组合数失控。"""
    oversized = [f"stat_{index}" for index in range(MAX_STAT_POOL_SIZE + 1)]

    with pytest.raises(ValidationError):
        CustomAlluvium(name="超长", skill_stats=oversized)


def test_stat_pool_at_limit_is_accepted():
    """上限本身是允许的：上限只用来兜异常数据，不该挡住正常使用。"""
    at_limit = [f"stat_{index}" for index in range(MAX_STAT_POOL_SIZE)]

    assert len(CustomAlluvium(name="刚好", skill_stats=at_limit).skill_stats) == (
        MAX_STAT_POOL_SIZE
    )
