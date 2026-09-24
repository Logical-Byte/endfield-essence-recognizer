"""评估工具函数——等级比较、权重计算等公共工具。

本模块仅保留被其他模块引用的纯工具函数。
分类逻辑在 classifier.py，认领逻辑在 claimer.py，日志组装在 log_builder.py。
"""

from itertools import accumulate

from endfield_essence_recognizer.game_data.models.v2 import StatType
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.profile import CUSTOM_ID_PREFIX
from endfield_essence_recognizer.schemas.user_setting import KeepBestMode

# ── 冷却脂消耗模式下的累计冷却脂权重 ──
# 从 1 级升到该等级所需的冷却脂总量（1/1/1 视作 0）
_GREASE_AFFIX_12 = tuple(
    accumulate((0, 0, 30, 60, 120, 250, 450))
)  # 索引 = 等级（1~6）
_GREASE_AFFIX_3 = tuple(accumulate((0, 0, 120, 300)))  # 索引 = 等级（1~3）

# ── 概率和值模式下的升级难度权重 ──
_WEIGHTS_AFFIX_12 = tuple(
    accumulate((0, 0, 1 / 0.6, 1 / 0.24, 1 / 0.109, 1 / 0.05, 1 / 0.027))
)  # 索引 = 等级（1~6）
_WEIGHTS_AFFIX_3 = tuple(accumulate((0, 0, 1 / 0.109, 1 / 0.042)))  # 索引 = 等级（1~3）

# ── 词条的语义顺序 ──
# 与武器的 stat1/stat2/stat3、profile 的 affix1/affix2/affix3 保持一致
_SEMANTIC_ORDER: tuple[StatType, ...] = (
    StatType.ATTRIBUTE,
    StatType.SECONDARY,
    StatType.SKILL,
)


def _grease_sum(
    levels: tuple[int, int, int], stat_types: list[StatType | None]
) -> float:
    """计算等级元组的冷却脂消耗总量（1/1/1 视作 0）。"""
    total = 0.0
    for lv, st in zip(levels, stat_types, strict=True):
        clamped_lv = min(
            max(lv, 0),
            len(_GREASE_AFFIX_12) - 1
            if st != StatType.SKILL
            else len(_GREASE_AFFIX_3) - 1,
        )
        if st == StatType.SKILL:
            total += _GREASE_AFFIX_3[clamped_lv]
        else:
            total += _GREASE_AFFIX_12[clamped_lv]
    return total


def _weighted_sum(
    levels: tuple[int, int, int], stat_types: list[StatType | None]
) -> float:
    """计算等级元组的加权和（按升级难度加权）。"""
    total = 0.0
    for lv, st in zip(levels, stat_types, strict=True):
        clamped_lv = min(
            max(lv, 0),
            len(_WEIGHTS_AFFIX_12) - 1
            if st != StatType.SKILL
            else len(_WEIGHTS_AFFIX_3) - 1,
        )
        if st == StatType.SKILL:
            total += _WEIGHTS_AFFIX_3[clamped_lv]
        else:
            total += _WEIGHTS_AFFIX_12[clamped_lv]
    return total


def _level_cmp(
    current: tuple[int, int, int],
    existing: tuple[int, int, int],
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
) -> int:
    """比较等级元组，返回 1（更优）/ 0（相等）/ -1（更差）。"""
    if mode == KeepBestMode.SUM:
        cs, es = sum(current), sum(existing)
        if cs > es:
            return 1
        if cs < es:
            return -1
        return 0
    if mode == KeepBestMode.GREASE:
        if stat_types is None:
            stat_types = [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL]
        cg, eg = _grease_sum(current, stat_types), _grease_sum(existing, stat_types)
        if cg > eg:
            return 1
        if cg < eg:
            return -1
        return 0
    if mode == KeepBestMode.WEIGHTED_SUM:
        if stat_types is None:
            stat_types = [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL]
        cw = _weighted_sum(current, stat_types)
        ew = _weighted_sum(existing, stat_types)
        if cw > ew:
            return 1
        if cw < ew:
            return -1
        return 0
    # 依次比对（默认）
    for c, e in zip(current, existing, strict=True):
        if c > e:
            return 1
        if c < e:
            return -1
    return 0


def compare_levels(
    current: tuple[int, int, int],
    existing: tuple[int, int, int],
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
) -> int:
    """比较等级元组的公开接口，供 API 路由调用。

    Returns:
        1（当前更优）/ 0（相等）/ -1（当前更差）
    """
    return _level_cmp(current, existing, mode, stat_types)


def _normalize_by_stat_type(
    stats: list[str | None],
    stat_types: list[StatType | None],
    levels: list[int | None],
) -> tuple[tuple[str | None, ...], list[StatType | None], tuple[int, int, int]]:
    """把识别位置顺序的词条三元组重排为语义顺序（属性、副属性、技能）。

    识别层按屏幕 ROI 位置 0/1/2 产出 stats/stat_types/levels，位置顺序不保证
    等于语义顺序；而武器的 stat1/2/3 与 profile 的 affix1/2/3 均按语义顺序存储。
    不归一化时，同一属性组合的基质会因词条显示顺序不同被算作不同分组各占名额，
    等级比较与落盘也会错位。

    语义类型未识别（None）或重复的位置，按原相对顺序补入剩余空槽。

    Args:
        stats: 按识别位置排列的属性 ID 列表。
        stat_types: 按识别位置排列的语义类型列表。
        levels: 按识别位置排列的等级列表（None 视作 1 级）。

    Returns:
        (语义顺序的属性组合 key, 语义顺序的类型列表, 语义顺序的等级元组)。
    """
    slots: list[int | None] = [None] * len(_SEMANTIC_ORDER)
    leftovers: list[int] = []
    for index, stat_type in enumerate(stat_types):
        slot = (
            _SEMANTIC_ORDER.index(stat_type) if stat_type in _SEMANTIC_ORDER else None
        )
        if slot is None or slots[slot] is not None:
            leftovers.append(index)
        else:
            slots[slot] = index

    # 类型未识别或重复的位置，按原顺序补入剩余空槽
    order: list[int] = []
    for slot_index in slots:
        order.append(leftovers.pop(0) if slot_index is None else slot_index)

    stat_key = tuple(stats[i] for i in order)
    ordered_types = [stat_types[i] for i in order]
    ordered_levels = (
        levels[order[0]] or 1,
        levels[order[1]] or 1,
        levels[order[2]] or 1,
    )
    return stat_key, ordered_types, ordered_levels


def _order_candidate_ids(
    matched_weapon_ids: set[str],
    weapon_priority_order: list[str] | None,
) -> list[str]:
    """排序候选 ID：自定义基质优先，其余按武器优先级。

    自定义基质与内置武器同时命中时，基质优先保存到自定义条目（视作独立武器），
    自定义达到上限后再回退到内置武器。
    """
    custom_ids = sorted(
        wid for wid in matched_weapon_ids if wid.startswith(CUSTOM_ID_PREFIX)
    )
    if not custom_ids:
        if weapon_priority_order:
            return [wid for wid in weapon_priority_order if wid in matched_weapon_ids]
        return sorted(matched_weapon_ids)
    custom_set = set(custom_ids)
    if weapon_priority_order:
        rest = [
            wid
            for wid in weapon_priority_order
            if wid in matched_weapon_ids and wid not in custom_set
        ]
    else:
        rest = sorted(wid for wid in matched_weapon_ids if wid not in custom_set)
    return custom_ids + rest


def _group_stat_key(
    matched_weapon_ids: set[str],
    static_game_data: StaticGameData | None,
) -> tuple:
    """取一组武器的属性组合作为 hashable key（同属性组合的孪生武器共享）。"""
    for wid in sorted(matched_weapon_ids):
        weapon = static_game_data.get_weapon(wid) if static_game_data else None
        if weapon:
            return (weapon.stat1_id, weapon.stat2_id, weapon.stat3_id)
    return tuple(sorted(matched_weapon_ids))
