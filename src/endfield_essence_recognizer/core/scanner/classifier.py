"""Layer 1：纯分类——判断基质是宝藏、养成材料还是跳过。

本模块是纯函数，不修改任何全局状态，不涉及认领/落盘逻辑。
"""

from endfield_essence_recognizer.core.recognition import RarityLabel
from endfield_essence_recognizer.core.scanner.models import (
    ClassificationResult,
    EssenceData,
    EssenceQuality,
)
from endfield_essence_recognizer.game_data.models.v2 import StatType
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.profile import CUSTOM_ID_PREFIX
from endfield_essence_recognizer.schemas.user_setting import (
    NonFiveStarBehavior,
    TreasureMatchMode,
    UserSetting,
)

STAT_SLOTS = ("attribute", "secondary", "skill")


def _custom_stat_display(setting: UserSetting, key: str) -> str | None:
    """返回自定义基质的显示名称；非自定义 ID 返回 None。"""
    if not key.startswith(CUSTOM_ID_PREFIX):
        return None
    for treasure_stat in setting.treasure_essence_stats:
        if treasure_stat.id and f"{CUSTOM_ID_PREFIX}{treasure_stat.id}" == key:
            return treasure_stat.name or "未命名"
    return key


def _format_stat_key(
    stat_key: tuple[str | None, ...], static_game_data: StaticGameData | None
) -> str:
    """格式化属性组合为可读字符串。"""
    if not static_game_data:
        return str(stat_key)
    parts = []
    for stat_id in stat_key:
        name = _stat_display_name(static_game_data, stat_id)
        if stat_id is not None:
            parts.append(f"{name}({stat_id})")
        else:
            parts.append(name)
    return "、".join(parts)


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
    treasure_stat,
    stats: list[str | None],
    stat_types: list[StatType | None],
    mode: TreasureMatchMode,
) -> bool:
    """检查基质是否匹配自定义宝藏基质条件。"""
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
    """评估五无瑕基质的高等级属性词条。"""
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


def classify_essence(
    data: EssenceData,
    setting: UserSetting,
    static_game_data: StaticGameData,
) -> ClassificationResult:
    """Layer 1：纯分类——判断基质是宝藏、养成材料还是跳过。

    不涉及认领、落盘或任何全局状态修改。

    Args:
        data: 原始识别数据（属性、等级、稀有度）。
        setting: 用户设置（阈值、自定义规则、拦截列表）。
        static_game_data: 静态游戏数据（武器、属性表）。

    Returns:
        ClassificationResult，包含分类结果和匹配的武器 ID。
    """
    # ── 非无瑕基质处理 ──
    if data.rarity != RarityLabel.FIVE:
        if setting.non_five_star_behavior == NonFiveStarBehavior.SKIP:
            return ClassificationResult(
                quality=EssenceQuality.SKIP,
            )
        if setting.non_five_star_behavior == NonFiveStarBehavior.STOP:
            return ClassificationResult(
                quality=EssenceQuality.SKIP,
                stop_scan=True,
            )
        if setting.non_five_star_behavior == NonFiveStarBehavior.HIGH_LEVEL_ONLY:
            is_high_level, high_level_info = _evaluate_non_five_star_high_level(
                data, setting, static_game_data
            )
            if is_high_level:
                return ClassificationResult(
                    quality=EssenceQuality.TREASURE,
                    is_high_level=True,
                    high_level_info=high_level_info,
                )
            return ClassificationResult(
                quality=EssenceQuality.TRASH,
                is_high_level=False,
            )

    # ── 高等级属性词条检测 ──
    is_high_level_treasure, high_level_info = _evaluate_high_level_treasure(
        data, setting, static_game_data
    )

    # ── 武器匹配 ──
    # 按语义类型构建武器匹配三元组（每种类型取第一个出现的 stat）
    type_to_stat: dict[StatType, str | None] = {}
    for stat_id, stat_type in zip(data.stats, data.stat_types, strict=True):
        if (
            stat_type is not None
            and stat_id is not None
            and stat_type not in type_to_stat
        ):
            type_to_stat[stat_type] = stat_id
    weapon_attr = type_to_stat.get(StatType.ATTRIBUTE)
    weapon_sec = type_to_stat.get(StatType.SECONDARY)
    weapon_skill = type_to_stat.get(StatType.SKILL)

    matched_weapon_ids = set(
        static_game_data.find_weapons_by_stats(weapon_attr, weapon_sec, weapon_skill)
    )

    # ── 自定义宝藏基质匹配 ──
    custom_treasure_name: str | None = None
    for treasure_stat in setting.treasure_essence_stats:
        if _matches_treasure_stats(
            treasure_stat,
            data.stats,
            data.stat_types,
            setting.treasure_essence_match_mode,
        ):
            candidate_ids = set(matched_weapon_ids)
            if treasure_stat.id:
                candidate_ids.add(f"{CUSTOM_ID_PREFIX}{treasure_stat.id}")
            non_trash_ids = candidate_ids - set(setting.trash_weapon_ids)
            custom_treasure_name = treasure_stat.name
            if non_trash_ids:
                return ClassificationResult(
                    quality=EssenceQuality.TREASURE,
                    matched_weapon_ids=non_trash_ids,
                    all_matched_weapon_ids=candidate_ids,
                    all_blocked=False,
                    is_high_level=is_high_level_treasure,
                    high_level_info=high_level_info,
                    custom_treasure_name=custom_treasure_name,
                )
            # 无 id 的自定义基质且未匹配内置武器
            return ClassificationResult(
                quality=EssenceQuality.TREASURE,
                matched_weapon_ids=set(),
                all_matched_weapon_ids=candidate_ids,
                all_blocked=True,
                is_high_level=is_high_level_treasure,
                high_level_info=high_level_info,
                custom_treasure_name=custom_treasure_name,
            )

    # ── 无匹配武器 ──
    if not matched_weapon_ids:
        if is_high_level_treasure:
            return ClassificationResult(
                quality=EssenceQuality.TREASURE,
                is_high_level=True,
                high_level_info=high_level_info,
            )
        return ClassificationResult(
            quality=EssenceQuality.TRASH,
        )

    # ── 有匹配武器：检查拦截列表 ──
    non_trash_weapon_ids = matched_weapon_ids - set(setting.trash_weapon_ids)

    if non_trash_weapon_ids:
        return ClassificationResult(
            quality=EssenceQuality.TREASURE,
            matched_weapon_ids=non_trash_weapon_ids,
            all_matched_weapon_ids=matched_weapon_ids,
            all_blocked=False,
            is_high_level=is_high_level_treasure,
            high_level_info=high_level_info,
        )

    # 所有匹配武器均被拦截
    if is_high_level_treasure:
        return ClassificationResult(
            quality=EssenceQuality.TREASURE,
            matched_weapon_ids=matched_weapon_ids,
            all_matched_weapon_ids=matched_weapon_ids,
            all_blocked=True,
            is_high_level=True,
            high_level_info=high_level_info,
        )

    return ClassificationResult(
        quality=EssenceQuality.TRASH,
        matched_weapon_ids=matched_weapon_ids,
        all_matched_weapon_ids=matched_weapon_ids,
        all_blocked=True,
        is_high_level=False,
    )
