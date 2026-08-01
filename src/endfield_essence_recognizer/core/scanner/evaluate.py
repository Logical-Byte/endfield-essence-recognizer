from collections.abc import Callable
from itertools import accumulate

from loguru import logger

from endfield_essence_recognizer.core.recognition import RarityLabel
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.game_data.models.v2 import StatType
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.user_setting import (
    EssenceStats,
    KeepBestMode,
    NonFiveStarBehavior,
    SameTypeGroupMode,
    TreasureMatchMode,
    UserSetting,
)

STAT_SLOTS = ("attribute", "secondary", "skill")

# 本轮扫描中通过 _claim_by_limit 认领的 (key, level)，用于级联判断。
_claimed_this_scan: set[tuple[str, tuple[int, int, int]]] = set()
# 本轮扫描中实际更新了 best levels 的 key，用于同步到引擎。
_updated_this_scan: set[str] = set()
# 本轮扫描中级联更新了 best levels 的 key（不增加计数，仅同步等级到引擎）。
_cascade_updated_this_scan: set[str] = set()


def reset_scan_claims() -> None:
    """在新一轮扫描开始时调用，清空本轮认领记录。"""
    _claimed_this_scan.clear()
    _updated_this_scan.clear()
    _cascade_updated_this_scan.clear()


def get_updated_weapon_ids() -> set[str]:
    """获取本轮扫描中实际更新了 best levels 的武器 ID。"""
    return _updated_this_scan.copy()


def get_cascade_updated_weapon_ids() -> set[str]:
    """获取本轮扫描中级联更新了 best levels 的武器 ID（仅等级，无计数）。"""
    return _cascade_updated_this_scan.copy()


# StatType → 对应 EssenceStats / 阈值配置中的字段名
_TYPE_TO_SLOT: dict[StatType, str] = {
    StatType.ATTRIBUTE: "attribute",
    StatType.SECONDARY: "secondary",
    StatType.SKILL: "skill",
}


def _get_threshold_for_type(
    stat_type: StatType | None,
    thresholds_by_type: dict[str, int],
) -> int | None:
    """根据 stat 的语义类型查找对应的判定阈值。"""
    if stat_type is None:
        return None
    slot = _TYPE_TO_SLOT.get(stat_type)
    if slot is None:
        return None
    return thresholds_by_type.get(slot)


# 冷却脂消耗模式下的累计冷却脂权重
# 从 1 级升到该等级所需的冷却脂总量（1/1/1 视作 0）
# 基础属性/附加属性（词条 1&2）：阈值 {1→2:30, 2→3:60, 3→4:120, 4→5:250, 5→6:450}
_GREASE_AFFIX_12 = tuple(
    accumulate((0, 0, 30, 60, 120, 250, 450))
)  # 索引 = 等级（1~6）
# 技能属性（词条 3）：阈值 {1→2:120, 2→3:300}
_GREASE_AFFIX_3 = tuple(accumulate((0, 0, 120, 300)))  # 索引 = 等级（1~3）

# 概率和值模式下的升级难度权重
# 累计期望基质数：从 1 级升到该等级所需的期望基质数量（等级越高越难升）
# 基础属性/附加属性（词条 1&2）：升级概率 {1→2:0.6, 2→3:0.24, 3→4:0.109, 4→5:0.05, 5→6:0.027}
_WEIGHTS_AFFIX_12 = tuple(
    accumulate((0, 0, 1 / 0.6, 1 / 0.24, 1 / 0.109, 1 / 0.05, 1 / 0.027))
)  # 索引 = 等级（1~6）
# 技能属性（词条 3）：升级概率 {1→2:0.109, 2→3:0.042}
_WEIGHTS_AFFIX_3 = tuple(accumulate((0, 0, 1 / 0.109, 1 / 0.042)))  # 索引 = 等级（1~3）


def _matches_by_mode(
    matches: list[bool], configured_count: int, mode: TreasureMatchMode
) -> bool:
    if configured_count == 0:
        return False
    if mode == TreasureMatchMode.ANY:
        return any(matches)
    if mode == TreasureMatchMode.ALL:
        return configured_count == len(STAT_SLOTS) and all(matches)
    return all(matches)


def _matches_treasure_stats(
    treasure_stat: EssenceStats,
    stats: list[str | None],
    stat_types: list[StatType | None],
    mode: TreasureMatchMode,
) -> bool:
    # 按类型构建查找表：type → 实际 stat_id
    type_to_actual: dict[StatType, str | None] = {}
    for stat_id, stat_type in zip(stats, stat_types, strict=True):
        if stat_type is not None and stat_type not in type_to_actual:
            type_to_actual[stat_type] = stat_id

    # 用户配置的期望值按类型查找
    configured_values = [
        treasure_stat.attribute,
        treasure_stat.secondary,
        treasure_stat.skill,
    ]
    expected_types = [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL]

    matches = [
        expected == type_to_actual.get(expected_type)
        for expected, expected_type in zip(
            configured_values, expected_types, strict=True
        )
        if expected is not None
    ]
    return _matches_by_mode(matches, len(matches), mode)


def _stat_display_name(static_game_data: StaticGameData, stat_id: str | None) -> str:
    if stat_id is None:
        return "未知属性"
    stat = static_game_data.get_stat(stat_id)
    return stat.name if stat is not None else stat_id


def _format_high_level_info(
    static_game_data: StaticGameData,
    stats: list[str | None],
    levels: list[int | None],
    indexes: list[int],
) -> str:
    parts = [
        f"{_stat_display_name(static_game_data, stats[index])}+{levels[index]}"
        for index in indexes
        if stats[index] is not None and levels[index] is not None
    ]
    if not parts:
        return ""
    return f"（含高等级属性词条：{'、'.join(parts)}）"


def _evaluate_high_level_treasure(
    data: EssenceData,
    setting: UserSetting,
    static_game_data: StaticGameData,
) -> tuple[bool, str]:
    if not setting.high_level_treasure_enabled:
        return False, ""

    stats = data.stats
    stat_types = data.stat_types
    levels = data.levels
    mode = setting.high_level_treasure_match_mode

    if mode == TreasureMatchMode.SUM:
        present_indexes = [
            i
            for i, (stat_id, level) in enumerate(zip(stats, levels, strict=True))
            if stat_id is not None and level is not None
        ]
        total = sum(levels[i] for i in present_indexes)  # type: ignore[misc]
        if total < setting.high_level_treasure_sum_threshold:
            return False, ""
        return True, _format_high_level_info(
            static_game_data, stats, levels, present_indexes
        )

    # 按类型构建阈值和 only_check 查找表
    thresholds_by_type: dict[str, int] = {
        "attribute": setting.high_level_treasure_attribute_threshold,
        "secondary": setting.high_level_treasure_secondary_threshold,
        "skill": setting.high_level_treasure_skill_threshold,
    }
    only_flags_by_type: dict[str, bool] = {
        "attribute": setting.high_level_treasure_only_check_attribute,
        "secondary": setting.high_level_treasure_only_check_secondary,
        "skill": setting.high_level_treasure_only_check_skill,
    }

    # 按每个位置的语义类型查找对应阈值进行判定
    original_slot_matches: list[bool] = []
    for stat_id, stat_type, level in zip(stats, stat_types, levels, strict=True):
        threshold = _get_threshold_for_type(stat_type, thresholds_by_type)
        if threshold is None or stat_id is None or level is None:
            original_slot_matches.append(False)
        else:
            original_slot_matches.append(level >= threshold)

    if mode == TreasureMatchMode.ONLY:
        # ONLY 模式：按类型分组，每种勾选的类型只要至少有一个词条达标即可
        type_has_match: dict[str, bool] = {}
        type_matched_indexes: dict[str, list[int]] = {}
        for i, (m, st) in enumerate(
            zip(original_slot_matches, stat_types, strict=True)
        ):
            if st is None:
                continue
            slot = _TYPE_TO_SLOT.get(st, "")
            if not only_flags_by_type.get(slot, False):
                continue
            if slot not in type_has_match:
                type_has_match[slot] = False
                type_matched_indexes[slot] = []
            if m:
                type_has_match[slot] = True
                type_matched_indexes[slot].append(i)

        eval_matches = list(type_has_match.values())
        matched_indexes = [
            idx
            for indexes in type_matched_indexes.values()
            if indexes  # 只包含至少有一个达标词条的类型
            for idx in indexes
        ]
    else:
        eval_matches = original_slot_matches
        if mode == TreasureMatchMode.ANY:
            matched_indexes = [i for i, m in enumerate(original_slot_matches) if m]
        else:
            matched_indexes = (
                list(range(len(STAT_SLOTS))) if all(original_slot_matches) else []
            )

    if not _matches_by_mode(eval_matches, len(eval_matches), mode):
        return False, ""

    return True, _format_high_level_info(
        static_game_data, stats, levels, matched_indexes
    )


def _evaluate_non_five_star_high_level(
    data: EssenceData,
    setting: UserSetting,
    static_game_data: StaticGameData,
) -> tuple[bool, str]:
    """评估非无瑕基质的高等级属性词条。

    如果启用了独立设置，使用非无暇基质专用的高等级判定设置；
    否则使用宝藏基质判定规则中的高等级设置。
    """
    # 判断是否使用独立设置
    if setting.non_five_star_separate_high_level_settings:
        thresholds_by_type: dict[str, int] = {
            "attribute": setting.non_five_star_high_level_attribute_threshold,
            "secondary": setting.non_five_star_high_level_secondary_threshold,
            "skill": setting.non_five_star_high_level_skill_threshold,
        }
        mode = setting.non_five_star_high_level_match_mode
        sum_threshold = setting.non_five_star_high_level_sum_threshold
        only_flags_by_type: dict[str, bool] = {
            "attribute": setting.non_five_star_high_level_only_check_attribute,
            "secondary": setting.non_five_star_high_level_only_check_secondary,
            "skill": setting.non_five_star_high_level_only_check_skill,
        }
    else:
        # 使用宝藏基质判定规则中的高等级设置
        if not setting.high_level_treasure_enabled:
            return False, ""
        thresholds_by_type = {
            "attribute": setting.high_level_treasure_attribute_threshold,
            "secondary": setting.high_level_treasure_secondary_threshold,
            "skill": setting.high_level_treasure_skill_threshold,
        }
        mode = setting.high_level_treasure_match_mode
        sum_threshold = setting.high_level_treasure_sum_threshold
        only_flags_by_type = {
            "attribute": setting.high_level_treasure_only_check_attribute,
            "secondary": setting.high_level_treasure_only_check_secondary,
            "skill": setting.high_level_treasure_only_check_skill,
        }

    stats = data.stats
    stat_types = data.stat_types
    levels = data.levels

    if mode == TreasureMatchMode.SUM:
        present_indexes = [
            i
            for i, (stat_id, level) in enumerate(zip(stats, levels, strict=True))
            if stat_id is not None and level is not None
        ]
        total = sum(levels[i] for i in present_indexes)  # type: ignore[misc]
        if total < sum_threshold:
            return False, ""
        return True, _format_high_level_info(
            static_game_data, stats, levels, present_indexes
        )

    # 按每个位置的语义类型查找对应阈值进行判定
    original_slot_matches: list[bool] = []
    for stat_id, stat_type, level in zip(stats, stat_types, levels, strict=True):
        threshold = _get_threshold_for_type(stat_type, thresholds_by_type)
        if threshold is None or stat_id is None or level is None:
            original_slot_matches.append(False)
        else:
            original_slot_matches.append(level >= threshold)

    if mode == TreasureMatchMode.ONLY:
        # ONLY 模式：按类型分组，每种勾选的类型只要至少有一个词条达标即可
        type_has_match: dict[str, bool] = {}
        type_matched_indexes: dict[str, list[int]] = {}
        for i, (m, st) in enumerate(
            zip(original_slot_matches, stat_types, strict=True)
        ):
            if st is None:
                continue
            slot = _TYPE_TO_SLOT.get(st, "")
            if not only_flags_by_type.get(slot, False):
                continue
            if slot not in type_has_match:
                type_has_match[slot] = False
                type_matched_indexes[slot] = []
            if m:
                type_has_match[slot] = True
                type_matched_indexes[slot].append(i)

        eval_matches = list(type_has_match.values())
        matched_indexes = [
            idx
            for indexes in type_matched_indexes.values()
            if indexes  # 只包含至少有一个达标词条的类型
            for idx in indexes
        ]
    else:
        eval_matches = original_slot_matches
        if mode == TreasureMatchMode.ANY:
            matched_indexes = [i for i, m in enumerate(original_slot_matches) if m]
        else:
            matched_indexes = (
                list(range(len(STAT_SLOTS))) if all(original_slot_matches) else []
            )

    if not _matches_by_mode(eval_matches, len(eval_matches), mode):
        return False, ""

    return True, _format_high_level_info(
        static_game_data, stats, levels, matched_indexes
    )


def _weighted_sum(
    levels: tuple[int, int, int], stat_types: list[StatType | None]
) -> float:
    """计算等级元组的加权和（按升级难度加权）。

    权重为从 1 级升到该等级所需的期望基质数，等级越高越难升，权重越大。
    根据每个词条的实际类型（stat_types）动态选择权重表：
    - ATTRIBUTE/SECONDARY（基础/附加）使用 _WEIGHTS_AFFIX_12
    - SKILL（技能）使用 _WEIGHTS_AFFIX_3
    """
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
        else:  # ATTRIBUTE 或 SECONDARY 或 None
            total += _WEIGHTS_AFFIX_12[clamped_lv]
    return total


def _grease_sum(
    levels: tuple[int, int, int], stat_types: list[StatType | None]
) -> float:
    """计算等级元组的冷却脂消耗总量（1/1/1 视作 0）。

    根据每个词条的实际类型（stat_types）动态选择权重表：
    - ATTRIBUTE/SECONDARY（基础/附加）使用 _GREASE_AFFIX_12
    - SKILL（技能）使用 _GREASE_AFFIX_3
    """
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
        else:  # ATTRIBUTE 或 SECONDARY 或 None
            total += _GREASE_AFFIX_12[clamped_lv]
    return total


def _level_cmp(
    current: tuple[int, int, int],
    existing: tuple[int, int, int],
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
) -> int:
    """比较等级元组，返回 1（更优）/ 0（相等）/ -1（更差）。

    Args:
        current: 当前基质的三个词条等级。
        existing: 已保存的最佳基质的三个词条等级。
        mode: 比较模式：
            - SEQUENTIAL: 从左到右逐维度比较 A → B → C（原有行为）。
            - SUM: 比较三个词条等级之和 A + B + C。
            - GREASE: 按从 1 级升到该等级所需的冷却脂总量比较（1/1/1 视作 0）。
            - WEIGHTED_SUM: 按升级难度加权比较，等级越高越难升，权重越大。
        stat_types: 词条类型列表，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表。
    """
    if mode == KeepBestMode.SUM:
        # 和值比对：直接比较三词条等级之和
        cs, es = sum(current), sum(existing)
        if cs > es:
            return 1
        if cs < es:
            return -1
        return 0
    if mode == KeepBestMode.GREASE:
        # 冷却脂消耗：按从 1 级升到该等级的冷却脂总量比较
        if stat_types is None:
            stat_types = [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL]
        cg, eg = _grease_sum(current, stat_types), _grease_sum(existing, stat_types)
        if cg > eg:
            return 1
        if cg < eg:
            return -1
        return 0
    if mode == KeepBestMode.WEIGHTED_SUM:
        # 概率和值：用升级期望基质数加权后比较
        if stat_types is None:
            stat_types = [StatType.ATTRIBUTE, StatType.SECONDARY, StatType.SKILL]
        cw = _weighted_sum(current, stat_types)
        ew = _weighted_sum(existing, stat_types)
        if cw > ew:
            return 1
        if cw < ew:
            return -1
        return 0
    # 依次比对（默认）：逐维度从左到右比较 A → B → C
    for c, e in zip(current, existing, strict=True):
        if c > e:
            return 1
        if c < e:
            return -1
    return 0


def _make_trash_by_limit(
    evaluation: EvaluationResult, current_count: int, limit: int
) -> EvaluationResult:
    """构造因达到数量上限而降级为养成材料的结果。"""
    return EvaluationResult(
        quality=EssenceQuality.TRASH,
        log_message=(
            "这个基质是<red><bold><underline>养成材料</></></>，"
            f"因为同类型宝藏基质已扫描到 {current_count} 个，达到设置上限 {limit} 个。"
        ),
        matched_weapons=evaluation.matched_weapons,
        matched_weapons_all_blocked=True,
        is_high_level=evaluation.is_high_level,
    )


def _claim_as_owned(
    setting: UserSetting,
    key: tuple[str | None, ...] | str,
    current_levels: tuple[int, int, int],
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
    _weapon_display: Callable[[str], str] = lambda k: k,
) -> bool:
    """留大弃小：判断当前基质是否属于该组"已保存"的那一枚（或其升级版）。

    - 相等：说明就是 profile 里保存的那一枚，在仍有跳过名额时直接认领（不占用数量上限）。
    - 更优：说明保存的那枚升级了，认领并把阈值提升到新等级，同时消耗一个已存名额。
    - 更差：返回 False，交由数量上限逻辑判断。

    Args:
        mode: 等级比较方式，由用户设置中的 same_type_keep_best_mode 决定。
        stat_types: 词条类型列表，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表。
    """
    best = setting._same_type_best_levels.get(key)
    if best is None:
        return False

    cmp = _level_cmp(current_levels, best, mode, stat_types)
    if cmp > 0:
        setting._same_type_best_levels[key] = current_levels
        if isinstance(key, str) and key.startswith("wpn_"):
            _updated_this_scan.add(key)
        skip = setting._same_type_equal_skips.get(key, 0)
        if skip > 0:
            setting._same_type_equal_skips[key] = skip - 1
        logger.debug(
            f"[留大弃小] {_weapon_display(key)} 基质等级 {current_levels} 优于已保存 {best}，"
            f"认领并提升阈值（剩余跳过名额: {skip - 1 if skip > 0 else 0}）"
        )
        return True
    if cmp == 0:
        skip = setting._same_type_equal_skips.get(key, 0)
        if skip > 0:
            setting._same_type_equal_skips[key] = skip - 1
            logger.debug(
                f"[留大弃小] {_weapon_display(key)} 基质等级 {current_levels} 等于已保存 {best}，"
                f"认领（剩余跳过名额: {skip - 1}）"
            )
            return True
        logger.debug(
            f"[留大弃小] {_weapon_display(key)} 基质等级 {current_levels} 等于已保存 {best}，"
            f"但跳过名额已用尽，不认领"
        )
    else:
        logger.debug(
            f"[留大弃小] {_weapon_display(key)} 基质等级 {current_levels} 劣于已保存 {best}，不认领"
        )
    return False


def _claim_by_limit(
    setting: UserSetting,
    key: tuple[str | None, ...] | str,
    current_levels: tuple[int, int, int],
    limit: int,
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
    _weapon_display: Callable[[str], str] = lambda k: k,
) -> bool:
    """按数量上限认领当前基质：未达上限则保留并计数，同时维护最佳等级。

    Args:
        mode: 等级比较方式，用于判断新基质是否比已记录的最佳等级更优。
        stat_types: 词条类型列表，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表。
    """
    count = setting._same_type_treasure_counts.get(key, 0)
    if count >= limit:
        return False
    best = setting._same_type_best_levels.get(key)
    if best is not None and _level_cmp(current_levels, best, mode, stat_types) < 0:
        logger.debug(
            f"[数量上限] {_weapon_display(key)} 基质等级 {current_levels} 劣于已保存 {best}，不认领"
        )
        return False
    setting._same_type_treasure_counts[key] = count + 1
    if best is None or _level_cmp(current_levels, best, mode, stat_types) > 0:
        setting._same_type_best_levels[key] = current_levels
        if isinstance(key, str) and key.startswith("wpn_"):
            _updated_this_scan.add(key)
    logger.debug(
        f"[数量上限] {_weapon_display(key)} 认领基质等级 {current_levels}，当前计数 {count + 1}/{limit}"
    )
    return True


def _apply_stat_group_limit(
    setting: UserSetting,
    evaluation: EvaluationResult,
    stat_key: tuple[str | None, ...],
    current_levels: tuple[int, int, int],
    limit: int,
    keep_best: bool,
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
    matched_weapon_ids: set[str] | None = None,
) -> EvaluationResult:
    """按基质分组（属性组合相同即为同类型）的限制逻辑。

    Args:
        mode: 等级比较方式，仅在 keep_best=True 时生效。
        stat_types: 词条类型列表，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表。
        matched_weapon_ids: 匹配的武器 ID 集合，用于同步更新追踪。
    """
    if keep_best and _claim_as_owned(
        setting, stat_key, current_levels, mode, stat_types
    ):
        return evaluation
    if _claim_by_limit(setting, stat_key, current_levels, limit, mode, stat_types):
        # 认领成功时，将匹配的武器加入更新集合，确保计数和等级同步到引擎
        if matched_weapon_ids:
            for weapon_id in matched_weapon_ids:
                _updated_this_scan.add(weapon_id)
        return evaluation
    count = setting._same_type_treasure_counts.get(stat_key, 0)
    logger.debug(f"[数量上限] {stat_key} 已达上限 {count}/{limit}，标记为养成材料")
    return _make_trash_by_limit(evaluation, count, limit)


def _cascade_freed_levels(
    setting: UserSetting,
    freed_levels: tuple[int, int, int],
    remaining_ids: list[str],
    limit: int,
    mode: KeepBestMode,
    stat_types: list[StatType | None] | None,
    _weapon_display: Callable[[str], str] = lambda k: k,
) -> None:
    """级联：将一把武器升级后释放的旧等级分配给剩余武器。

    仅更新 _same_type_best_levels（不增加计数），用于后续非降级过滤。
    级联武器记录到 _cascade_updated_this_scan，引擎会同步等级但不同步计数。
    """
    for wid in remaining_ids:
        old_best = setting._same_type_best_levels.get(wid)
        # 检查释放的等级是否优于当前最佳
        if (
            old_best is not None
            and _level_cmp(freed_levels, old_best, mode, stat_types) <= 0
        ):
            continue  # 不优于，跳过
        # 认领释放的等级（不增加计数）
        setting._same_type_best_levels[wid] = freed_levels
        _cascade_updated_this_scan.add(wid)
        logger.debug(
            f"[级联] 武器 {_weapon_display(wid)} 认领释放的等级 {freed_levels}"
        )
        break  # 只分配给一把武器


def _apply_weapon_group_limit(
    setting: UserSetting,
    evaluation: EvaluationResult,
    matched_weapon_ids: set[str],
    current_levels: tuple[int, int, int],
    limit: int,
    keep_best: bool,
    mode: KeepBestMode = KeepBestMode.SEQUENTIAL,
    stat_types: list[StatType | None] | None = None,
    weapon_essence_levels: dict[str, tuple[int, int, int]] | None = None,
    weapon_priority_order: list[str] | None = None,
    static_game_data: StaticGameData | None = None,
) -> EvaluationResult:
    """按武器分组（每把武器独立计数）的限制逻辑。

    Args:
        mode: 等级比较方式，仅在 keep_best=True 时生效。
        stat_types: 词条类型列表，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表。
        weapon_essence_levels: 各武器当前基质等级，用于非降级原则过滤。
        weapon_priority_order: 武器优先级排序（高优先级在前），用于决定分配顺序。
    """
    if weapon_priority_order:
        weapon_ids = [w for w in weapon_priority_order if w in matched_weapon_ids]
    else:
        weapon_ids = sorted(matched_weapon_ids)

    # 武器名称显示工具：输出 "武器名称(武器ID)" 格式
    def _display(wid: str) -> str:
        if static_game_data:
            weapon = static_game_data.get_weapon(wid)
            if weapon:
                return f"{weapon.name}({wid})"
        return wid

    # 过滤掉基质等级不满足非降级原则的武器
    if weapon_essence_levels and setting.same_type_non_downgrade_filter:
        upgradeable_ids = []
        for wid in weapon_ids:
            existing = weapon_essence_levels.get(wid)
            if existing is None:
                upgradeable_ids.append(wid)
                logger.debug(f"[非降级] 武器 {_display(wid)} 无已保存基质，通过")
            elif (
                current_levels[0] >= existing[0]
                and current_levels[1] >= existing[1]
                and current_levels[2] >= existing[2]
            ):
                upgradeable_ids.append(wid)
                logger.debug(
                    f"[非降级] 武器 {_display(wid)} 已保存等级 {existing}，"
                    f"基质等级 {current_levels}，满足非降级原则，通过"
                )
            else:
                # 找出具体哪些维度不满足
                dims = ["词条1", "词条2", "词条3"]
                failed = [
                    f"{dims[i]}({current_levels[i]}<{existing[i]})"
                    for i in range(3)
                    if current_levels[i] < existing[i]
                ]
                logger.debug(
                    f"[非降级] 武器 {_display(wid)} 已保存等级 {existing}，"
                    f"基质等级 {current_levels}，"
                    f"不满足非降级原则（{', '.join(failed)}），过滤"
                )
        weapon_ids = upgradeable_ids

    if not weapon_ids:
        return EvaluationResult(
            quality=EssenceQuality.TRASH,
            log_message=(
                "这个基质是<red><bold><underline>养成材料</></></>，"
                "因为它无法升级任何匹配武器的已有基质（不满足非降级原则）。"
            ),
            matched_weapons=evaluation.matched_weapons,
            matched_weapons_all_blocked=True,
            is_high_level=evaluation.is_high_level,
        )

    # 矩阵只分配给一把武器（优先级最高的可接受武器）。
    # 留大弃小：如果该武器已有更优或相等的保存等级，直接认领（不占数量上限）。
    # 数量上限：如果未达上限，认领并计数。
    # 当武器通过留大弃小升级时，释放的旧等级会级联给剩余武器。
    for i, weapon_id in enumerate(weapon_ids):
        old_best = setting._same_type_best_levels.get(weapon_id)
        if keep_best and _claim_as_owned(
            setting, weapon_id, current_levels, mode, stat_types, _display
        ):
            # 留大弃小认领成功，检查是否是升级（而非相等跳过）
            if old_best is not None and old_best != current_levels:
                # 是升级：释放旧等级给剩余武器
                # 仅当旧等级是本轮扫描中通过 _claim_by_limit 认领的才级联
                if (weapon_id, old_best) in _claimed_this_scan:
                    remaining = weapon_ids[i + 1 :]
                    if remaining:
                        _cascade_freed_levels(
                            setting,
                            old_best,
                            remaining,
                            limit,
                            mode,
                            stat_types,
                            _display,
                        )
            return evaluation
        if _claim_by_limit(
            setting, weapon_id, current_levels, limit, mode, stat_types, _display
        ):
            _claimed_this_scan.add((weapon_id, current_levels))
            _updated_this_scan.add(
                weapon_id
            )  # 认领成功时加入更新集合，确保计数和等级同步到引擎
            return evaluation

    # 所有匹配武器都已达上限
    logger.debug(
        f"[数量上限] 所有可选武器 {', '.join(_display(w) for w in weapon_ids)} 均已达上限 {limit}，标记为养成材料"
    )
    return _make_trash_by_limit(evaluation, limit, limit)


def _apply_same_type_treasure_limit(
    data: EssenceData,
    setting: UserSetting,
    evaluation: EvaluationResult,
    matched_weapon_ids: set[str] | None = None,
    weapon_essence_levels: dict[str, tuple[int, int, int]] | None = None,
    weapon_priority_order: list[str] | None = None,
    static_game_data: StaticGameData | None = None,
) -> EvaluationResult:
    if evaluation.quality != EssenceQuality.TREASURE:
        return evaluation

    # 当限制功能关闭时，仍需将匹配的武器加入更新集合，确保扫描结果同步到引擎
    if not setting.same_type_treasure_limit_enabled:
        if matched_weapon_ids:
            current_levels = (
                data.levels[0] or 1,
                data.levels[1] or 1,
                data.levels[2] or 1,
            )
            stat_types = data.stat_types
            mode = setting.same_type_keep_best_mode
            for weapon_id in matched_weapon_ids:
                _updated_this_scan.add(weapon_id)
                # 保留同武器中等级最高的基质，后续写回宝藏基质配置时以最高等级为准
                best = setting._same_type_best_levels.get(weapon_id)
                if (
                    best is None
                    or _level_cmp(current_levels, best, mode, stat_types) > 0
                ):
                    setting._same_type_best_levels[weapon_id] = current_levels
                # 累计每把武器认领的基质数量，用于最终统计输出
                setting._same_type_treasure_counts[weapon_id] = (
                    setting._same_type_treasure_counts.get(weapon_id, 0) + 1
                )
        return evaluation

    limit = setting.same_type_treasure_limit
    keep_best = setting.same_type_keep_best
    mode = (
        setting.same_type_keep_best_mode
    )  # 留大弃小的等级比较方式（依次比对/和值比对/冷却脂消耗/概率和值）
    current_levels = (
        data.levels[0] or 1,
        data.levels[1] or 1,
        data.levels[2] or 1,
    )
    # 传递词条类型，用于 GREASE 和 WEIGHTED_SUM 模式下动态选择权重表
    stat_types = data.stat_types

    if (
        setting.same_type_group_mode == SameTypeGroupMode.BY_WEAPON
        and matched_weapon_ids
    ):
        return _apply_weapon_group_limit(
            setting,
            evaluation,
            matched_weapon_ids,
            current_levels,
            limit,
            keep_best,
            mode,
            stat_types,
            weapon_essence_levels,
            weapon_priority_order,
            static_game_data,
        )

    # 默认按基质分组（包括自定义基质匹配和无匹配武器的情况）
    stat_key = tuple(data.stats)
    return _apply_stat_group_limit(
        setting,
        evaluation,
        stat_key,
        current_levels,
        limit,
        keep_best,
        mode,
        stat_types,
        matched_weapon_ids,
    )


def evaluate_essence(
    data: EssenceData,
    setting: UserSetting,
    static_game_data: StaticGameData,
    weapon_essence_levels: dict[str, tuple[int, int, int]] | None = None,
    weapon_priority_order: list[str] | None = None,
) -> EvaluationResult:
    """
    Pure function to judge the quality of an essence based on settings and game data.

    Logic:
    1. Checks high-level attributes thresholds (if enabled).
    2. Checks custom treasure stats (if configured).
    3. Matches against game data (weapons).
    4. Cross-references matched weapons with user's 'trash_weapon_ids'.
    5. Constructs the user-facing log message with color tags.

    Args:
        data: The raw recognition data (stats, levels).
        setting: The current user settings (thresholds, custom rules).
        static_game_data: The static game data for reference.
    Returns:
        EvaluationResult containing the decision, log message, and reasoning.
    """
    if data.rarity != RarityLabel.FIVE:
        if setting.non_five_star_behavior == NonFiveStarBehavior.SKIP:
            return EvaluationResult(
                quality=EssenceQuality.SKIP,
                log_message="这个基质是<dim>非无瑕基质</>，已根据设置跳过处理。",
            )
        if setting.non_five_star_behavior == NonFiveStarBehavior.STOP:
            return EvaluationResult(
                quality=EssenceQuality.SKIP,
                log_message="这个基质是<dim>非无瑕基质</>，已根据设置结束本次扫描。",
                stop_scan=True,
            )
        if setting.non_five_star_behavior == NonFiveStarBehavior.HIGH_LEVEL_ONLY:
            # 仅对非无瑕基质进行高等级属性词条判定，不判定武器匹配
            is_high_level, high_level_info = _evaluate_non_five_star_high_level(
                data, setting, static_game_data
            )
            if is_high_level:
                return _apply_same_type_treasure_limit(
                    data,
                    setting,
                    EvaluationResult(
                        quality=EssenceQuality.TREASURE,
                        log_message=f"这个基质是<green><bold><underline>宝藏</></></>（非无瑕基质），因为它有高等级属性词条{high_level_info}。",
                        is_high_level=True,
                    ),
                    weapon_essence_levels=weapon_essence_levels,
                    static_game_data=static_game_data,
                )
            else:
                return EvaluationResult(
                    quality=EssenceQuality.TRASH,
                    log_message="这个基质是<red><bold><underline>养成材料</></></>（非无瑕基质），它没有高等级属性词条。",
                    is_high_level=False,
                )

    stats = data.stats
    stat_types = data.stat_types

    is_high_level_treasure, high_level_info = _evaluate_high_level_treasure(
        data, setting, static_game_data
    )

    # 按语义类型构建武器匹配三元组（每种类型取第一个出现的 stat）
    # 如果某类型缺失或重复，对应的字段为 None
    type_to_stat: dict[StatType, str | None] = {}
    for stat_id, stat_type in zip(stats, stat_types, strict=True):
        if (
            stat_type is not None
            and stat_id is not None
            and stat_type not in type_to_stat
        ):
            type_to_stat[stat_type] = stat_id
    weapon_attr = type_to_stat.get(StatType.ATTRIBUTE)
    weapon_sec = type_to_stat.get(StatType.SECONDARY)
    weapon_skill = type_to_stat.get(StatType.SKILL)

    # 尝试匹配已实装武器
    matched_weapon_ids = set(
        static_game_data.find_weapons_by_stats(weapon_attr, weapon_sec, weapon_skill)
    )

    # 尝试匹配用户自定义的宝藏基质条件
    for treasure_stat in setting.treasure_essence_stats:
        if _matches_treasure_stats(
            treasure_stat, stats, stat_types, setting.treasure_essence_match_mode
        ):
            # 显示自定义基质名称，使用橙色（六星颜色）
            custom_name = treasure_stat.name or "未命名"
            return _apply_same_type_treasure_limit(
                data,
                setting,
                EvaluationResult(
                    quality=EssenceQuality.TREASURE,
                    log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它符合自定义基质 <fg #FF7100><bold>{custom_name}</></> 的条件{high_level_info}。",
                    is_high_level=is_high_level_treasure,
                ),
                matched_weapon_ids=matched_weapon_ids,
                weapon_essence_levels=weapon_essence_levels,
                weapon_priority_order=weapon_priority_order,
                static_game_data=static_game_data,
            )

    if not matched_weapon_ids:
        # 未匹配到任何已实装武器
        if is_high_level_treasure:
            return _apply_same_type_treasure_limit(
                data,
                setting,
                EvaluationResult(
                    quality=EssenceQuality.TREASURE,
                    log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。<dim>（但不匹配任何已实装武器）</>",
                    is_high_level=True,
                ),
                weapon_essence_levels=weapon_essence_levels,
                static_game_data=static_game_data,
            )
        else:
            return EvaluationResult(
                quality=EssenceQuality.TRASH,
                log_message="这个基质是<red><bold><underline>养成材料</></></>，它不匹配任何已实装武器。",
                is_high_level=False,
            )

    # 检查匹配到的武器中，是否有不在 trash_weapon_ids 中的
    non_trash_weapon_ids = matched_weapon_ids - set(setting.trash_weapon_ids)

    def format_weapon_description(weapon_id: str) -> str:
        """格式化武器描述，如`名称（稀有度★ 类型）`"""
        weapon = static_game_data.get_weapon(weapon_id)
        if not weapon:
            return f"<bold>{weapon_id}</>"

        weapon_type = static_game_data.get_weapon_type(weapon.weapon_type)
        type_name = weapon_type.name if weapon_type else "未知类型"

        rarity_color = static_game_data.get_rarity_color(weapon.rarity)
        return f"<fg {rarity_color}><bold>{weapon.name}（{weapon.rarity}★ {type_name}）</></>"

    if non_trash_weapon_ids:
        # 只要有一个匹配武器未被拦截，就是宝藏

        # 输出所有匹配到且未被拦截的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in non_trash_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        return _apply_same_type_treasure_limit(
            data,
            setting,
            EvaluationResult(
                quality=EssenceQuality.TREASURE,
                log_message=f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器{weapons_description_str}{high_level_info}。",
                matched_weapons=non_trash_weapon_ids,
                matched_weapons_all_blocked=False,
                is_high_level=is_high_level_treasure,
            ),
            matched_weapon_ids=non_trash_weapon_ids,
            weapon_essence_levels=weapon_essence_levels,
            weapon_priority_order=weapon_priority_order,
            static_game_data=static_game_data,
        )
    else:
        # 所有匹配到的武器都在 trash_weapon_ids 中

        # 输出所有匹配到的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in matched_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        if is_high_level_treasure:
            return _apply_same_type_treasure_limit(
                data,
                setting,
                EvaluationResult(
                    quality=EssenceQuality.TREASURE,
                    log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。<yellow>即使它匹配的所有武器{weapons_description_str}均已被用户手动拦截。</>",
                    matched_weapons=matched_weapon_ids,
                    matched_weapons_all_blocked=True,
                    is_high_level=True,
                ),
                matched_weapon_ids=matched_weapon_ids,
                weapon_essence_levels=weapon_essence_levels,
                weapon_priority_order=weapon_priority_order,
                static_game_data=static_game_data,
            )
        else:
            return EvaluationResult(
                quality=EssenceQuality.TRASH,
                log_message=f"这个基质虽然匹配武器{weapons_description_str}，但匹配的所有武器均已被用户手动拦截，因此这个基质是<red><bold><underline>养成材料</></></>。",
                matched_weapons=matched_weapon_ids,
                matched_weapons_all_blocked=True,
                is_high_level=False,
            )
