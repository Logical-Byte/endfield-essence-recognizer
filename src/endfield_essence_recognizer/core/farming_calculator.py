"""
刷取建议计算器。

根据游戏的概率系统，计算将宝藏基质词条升级到目标等级所需的预期刷取次数。

关键参数：
- 使用刻写券：每次刷取掉落 3 个完美基质
- 每次词条升级尝试消耗 1 个随机完美基质（任何武器的基质都可以）
- 升级成功率：
  - 词条 1&2（属性/副属性）：1→2(60%), 2→3(24%), 3→4(10.9%), 4→5(5%), 5→6(2.7%)
  - 词条 3（技能）：1→2(10.9%), 2→3(4.2%)
- 失败的升级给予 10 冷却脂
- 冷却脂可以在达到阈值时保证成功：
  - 词条 1&2：1→2(30), 2→3(60), 3→4(120), 4→5(250), 5→6(450)
  - 词条 3：1→2(120), 2→3(300)

注意：此计算器假设用户已经拥有该武器的宝藏基质，只需要任意完美基质来进行强化。
如果需要刷取特定武器的基质，则需要额外考虑 1/24 的掉落概率。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- 常量 ---

ESSENCES_PER_RUN = 3
"""每次刷取掉落的完美基质数量（使用刻写券）。"""

# 升级成功概率：等级 -> 从该等级升级到下一等级的成功概率
UPGRADE_PROBS_AFFIX_12: dict[int, float] = {
    1: 0.600,
    2: 0.240,
    3: 0.109,
    4: 0.050,
    5: 0.027,
}
"""词条 1&2 的升级概率。"""

UPGRADE_PROBS_AFFIX_3: dict[int, float] = {
    1: 0.109,
    2: 0.042,
}
"""词条 3 的升级概率。"""

# 冷却脂阈值：等级 -> 保证从该等级升级到下一等级所需的冷却脂
GREASE_THRESHOLD_AFFIX_12: dict[int, int] = {
    1: 30,
    2: 60,
    3: 120,
    4: 250,
    5: 450,
}
"""词条 1&2：每个等级的冷却脂阈值。"""

GREASE_THRESHOLD_AFFIX_3: dict[int, int] = {
    1: 120,
    2: 300,
}
"""词条 3：每个等级的冷却脂阈值。"""

GREASE_PER_FAIL = 10
"""每次失败的升级尝试获得的冷却脂。"""


@dataclass
class UpgradeStepDetail:
    """单个等级升级步骤的详细信息。"""

    from_level: int
    """此步骤的起始等级。"""

    to_level: int
    """此步骤的目标等级。"""

    success_prob: float
    """每次尝试的成功概率。"""

    grease_threshold: int
    """保证成功所需的冷却脂。"""

    expected_attempts: float
    """此步骤的预期升级尝试次数。"""

    expected_essences: float
    """预期消耗的基质数量（等于预期尝试次数）。"""

    expected_grease_gained: float
    """从失败中获得的预期冷却脂。"""

    expected_grease_used: float
    """预期消耗的冷却脂（仅当所有尝试都失败时）。"""

    use_grease_at: int | None = None
    """如果设置，在此次数的失败后使用冷却脂保证。"""


@dataclass
class AffixUpgradeResult:
    """将单个词条从当前等级升级到目标等级的结果。"""

    affix_name: str
    """词条名称（例如"基础属性"、"附加属性"、"技能属性"）。"""

    current_level: int
    """当前词条等级。"""

    target_level: int
    """目标词条等级。"""

    expected_attempts: float = 0.0
    """预期的总升级尝试次数。"""

    expected_essences_consumed: float = 0.0
    """预期消耗的总基质数量（每次尝试消耗 1 个）。"""

    expected_grease_gained: float = 0.0
    """从失败中获得的总预期冷却脂。"""

    expected_grease_used: float = 0.0
    """使用的总预期冷却脂（来自保证成功）。"""

    steps: list[UpgradeStepDetail] = field(default_factory=list)
    """每个步骤的详细分解。"""


@dataclass
class FarmingRecommendation:
    """完整的刷取建议。"""

    weapon_name: str
    """武器名称。"""

    weapon_id: str
    """武器 ID。"""

    affix_results: list[AffixUpgradeResult] = field(default_factory=list)
    """每个词条的结果。"""

    total_expected_essences: float = 0.0
    """所有词条所需的总预期基质数量。"""

    total_expected_runs: float = 0.0
    """所需的总预期刷取次数。"""

    current_levels: tuple[int, int, int] = (1, 1, 1)
    """当前词条等级（词条1、词条2、词条3）。"""

    target_levels: tuple[int, int, int] = (6, 6, 3)
    """目标词条等级（词条1、词条2、词条3）。"""


def _compute_single_step(
    success_prob: float,
    grease_threshold: int,
    from_level: int = 0,
    to_level: int = 0,
) -> UpgradeStepDetail:
    """
    计算单个等级升级步骤的预期尝试次数和冷却脂。

    策略：尝试升级直到成功或积累足够的冷却脂来保证成功。

    当我们限制在 ``max_attempts`` 次尝试时的预期尝试次数为：
        E[attempts] = (1 - fail_prob^max_attempts) / success_prob
    其中 ``max_attempts = ceil(grease_threshold / GREASE_PER_FAIL)``。

    Args:
        success_prob: 每次尝试的成功概率。
        grease_threshold: 保证成功所需的冷却脂。
        from_level: 此步骤的起始等级。
        to_level: 此步骤的目标等级。

    Returns:
        包含计算值的 UpgradeStepDetail。
    """
    fail_prob = 1 - success_prob
    max_attempts = (grease_threshold + GREASE_PER_FAIL - 1) // GREASE_PER_FAIL
    # ceil(grease_threshold / GREASE_PER_FAIL)

    # 预期尝试次数 = sum_{i=0}^{max_attempts-1} fail_prob^i
    #              = (1 - fail_prob^max_attempts) / success_prob
    if success_prob > 0:
        expected_attempts = (1 - fail_prob**max_attempts) / success_prob
    else:
        expected_attempts = max_attempts

    # 预期失败次数：数值计算为
    #   (i-1) * P(第 i 次尝试首次成功) 对 i=1..max_attempts 求和
    #   + max_attempts * P(全部失败)
    expected_failures = 0.0
    for attempt_index in range(1, max_attempts + 1):
        prob_first_success = success_prob * fail_prob ** (attempt_index - 1)
        expected_failures += (attempt_index - 1) * prob_first_success
    prob_all_fail = fail_prob**max_attempts
    expected_failures += max_attempts * prob_all_fail

    grease_gained = expected_failures * GREASE_PER_FAIL
    # 正常升级时不自动使用冷却脂，只有用户主动选择时才使用
    grease_used = 0

    return UpgradeStepDetail(
        from_level=from_level,
        to_level=to_level,
        success_prob=success_prob,
        grease_threshold=grease_threshold,
        expected_attempts=expected_attempts,
        expected_essences=expected_attempts,
        expected_grease_gained=grease_gained,
        expected_grease_used=grease_used,
        use_grease_at=max_attempts if prob_all_fail > 0 else None,
    )


def _compute_upgrade_steps(
    current: int,
    target: int,
    upgrade_probs: dict[int, float],
    grease_thresholds: dict[int, int],
    affix_name: str,
) -> AffixUpgradeResult:
    """
    计算将词条从当前等级升级到目标等级的预期尝试次数和基质数量。

    Args:
        current: 当前词条等级。
        target: 目标词条等级。
        upgrade_probs: 从等级到成功概率的映射。
        grease_thresholds: 从等级到冷却脂阈值的映射。
        affix_name: 词条的显示名称。

    Returns:
        包含每个步骤详细分解的 AffixUpgradeResult。
    """
    result = AffixUpgradeResult(
        affix_name=affix_name,
        current_level=current,
        target_level=target,
    )

    if current >= target:
        return result

    total_attempts = 0.0
    total_essences = 0.0
    total_grease_gained = 0.0
    total_grease_used = 0.0

    for level in range(current, target):
        success_prob = upgrade_probs.get(level)
        grease_threshold = grease_thresholds.get(level)

        if success_prob is None or grease_threshold is None:
            break

        step = _compute_single_step(
            success_prob, grease_threshold, from_level=level, to_level=level + 1
        )
        result.steps.append(step)

        total_attempts += step.expected_attempts
        # 每个步骤的基质消耗向上取整（不能消耗0.6个基质，必须是1个）
        total_essences += math.ceil(step.expected_essences)
        # 冷却脂获得/消耗取最接近的10的倍数
        total_grease_gained += round(step.expected_grease_gained / 10) * 10
        total_grease_used += round(step.expected_grease_used / 10) * 10

    result.expected_attempts = total_attempts
    result.expected_essences_consumed = total_essences
    result.expected_grease_gained = total_grease_gained
    result.expected_grease_used = total_grease_used

    return result


def compute_farming_recommendation(
    weapon_id: str,
    weapon_name: str,
    current_levels: tuple[int, int, int],
    target_levels: tuple[int, int, int],
) -> FarmingRecommendation:
    """
    计算升级武器宝藏基质的刷取建议。

    Args:
        weapon_id: 武器 ID。
        weapon_name: 武器显示名称。
        current_levels: 当前词条等级（词条1、词条2、词条3）。
        target_levels: 目标词条等级（词条1、词条2、词条3）。

    Returns:
        包含详细分解的 FarmingRecommendation。

    Raises:
        ValueError: 如果等级值超出有效范围。
    """
    # 验证 current_levels
    if not (
        1 <= current_levels[0] <= 6
        and 1 <= current_levels[1] <= 6
        and 1 <= current_levels[2] <= 3
    ):
        raise ValueError(
            f"Invalid current_levels: {current_levels}. Expected (1-6, 1-6, 1-3)"
        )

    # 验证 target_levels
    if not (
        1 <= target_levels[0] <= 6
        and 1 <= target_levels[1] <= 6
        and 1 <= target_levels[2] <= 3
    ):
        raise ValueError(
            f"Invalid target_levels: {target_levels}. Expected (1-6, 1-6, 1-3)"
        )

    # 验证 current <= target
    if (
        current_levels[0] > target_levels[0]
        or current_levels[1] > target_levels[1]
        or current_levels[2] > target_levels[2]
    ):
        raise ValueError(
            f"current_levels {current_levels} must not exceed target_levels {target_levels}"
        )

    recommendation = FarmingRecommendation(
        weapon_name=weapon_name,
        weapon_id=weapon_id,
        current_levels=current_levels,
        target_levels=target_levels,
    )

    # 词条 1（属性）：等级 1-6
    recommendation.affix_results.append(
        _compute_upgrade_steps(
            current=current_levels[0],
            target=target_levels[0],
            upgrade_probs=UPGRADE_PROBS_AFFIX_12,
            grease_thresholds=GREASE_THRESHOLD_AFFIX_12,
            affix_name="基础属性",
        )
    )

    # 词条 2（副属性）：等级 1-6
    recommendation.affix_results.append(
        _compute_upgrade_steps(
            current=current_levels[1],
            target=target_levels[1],
            upgrade_probs=UPGRADE_PROBS_AFFIX_12,
            grease_thresholds=GREASE_THRESHOLD_AFFIX_12,
            affix_name="附加属性",
        )
    )

    # 词条 3（技能）：等级 1-3
    recommendation.affix_results.append(
        _compute_upgrade_steps(
            current=current_levels[2],
            target=target_levels[2],
            upgrade_probs=UPGRADE_PROBS_AFFIX_3,
            grease_thresholds=GREASE_THRESHOLD_AFFIX_3,
            affix_name="技能属性",
        )
    )

    # 总基质数：每次升级尝试消耗 1 个随机完美基质（任何武器的基质都可以）
    total_essences = sum(
        affix_result.expected_essences_consumed
        for affix_result in recommendation.affix_results
    )
    recommendation.total_expected_essences = total_essences

    # 刷取次数：每次刷取掉落 ESSENCES_PER_RUN 个完美基质，可以直接用于强化
    # 假设用户已经拥有该武器的宝藏基质，只需要任意基质来强化
    if ESSENCES_PER_RUN > 0:
        recommendation.total_expected_runs = total_essences / ESSENCES_PER_RUN
    else:
        recommendation.total_expected_runs = float("inf")

    return recommendation
