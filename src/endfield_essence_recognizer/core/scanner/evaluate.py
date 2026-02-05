from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.models.user_setting import UserSetting


def evaluate_essence(data: EssenceData, setting: UserSetting) -> EvaluationResult:
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

    Returns:
        EvaluationResult containing the decision, log message, and reasoning.
    """
    from endfield_essence_recognizer.game_data import (
        gem_table,
        get_translation,
        weapon_basic_table,
    )
    from endfield_essence_recognizer.game_data.item import get_item_name
    from endfield_essence_recognizer.game_data.weapon import (
        get_gem_tag_name,
        weapon_stats_dict,
        weapon_type_int_to_translation_key,
    )

    stats = data.stats
    levels = data.levels

    # 检查属性等级：如果启用了高等级判定，记录是否为高等级宝藏
    is_high_level_treasure = False
    high_level_info = ""
    if setting.high_level_treasure_enabled:
        # stats 的顺序是 [基础属性, 附加属性, 技能属性]，对应 termType [0, 1, 2]
        thresholds = [
            setting.high_level_treasure_attribute_threshold,  # 基础属性阈值
            setting.high_level_treasure_secondary_threshold,  # 附加属性阈值
            setting.high_level_treasure_skill_threshold,  # 技能属性阈值
        ]
        for stat, level in zip(stats, levels, strict=True):
            if stat is not None and level is not None:
                gem = gem_table.get(stat)
                if gem is not None:
                    threshold = thresholds[gem["termType"]]
                    if level >= threshold:
                        is_high_level_treasure = True
                        high_level_info = f"（含高等级属性词条：{get_gem_tag_name(stat, 'CN')}+{level}）"
                        break

    # 尝试匹配用户自定义的宝藏基质条件
    for treasure_stat in setting.treasure_essence_stats:
        if (
            treasure_stat.attribute in stats
            and treasure_stat.secondary in stats
            and treasure_stat.skill in stats
        ):
            return EvaluationResult(
                quality=EssenceQuality.TREASURE,
                log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它符合你设定的宝藏基质条件{high_level_info}。",
                is_high_level=is_high_level_treasure,
            )

    # 尝试匹配已实装武器
    matched_weapon_ids: set[str] = set()
    for weapon_id in weapon_basic_table:
        weapon_stats = weapon_stats_dict[weapon_id]
        if (
            weapon_stats["attribute"] == stats[0]
            and weapon_stats["secondary"] == stats[1]
            and weapon_stats["skill"] == stats[2]
        ):
            matched_weapon_ids.add(weapon_id)

    if not matched_weapon_ids:
        # 未匹配到任何已实装武器
        if is_high_level_treasure:
            return EvaluationResult(
                quality=EssenceQuality.TREASURE,
                log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。<dim>（但不匹配任何已实装武器）</>",
                is_high_level=True,
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
        weapon_basic = weapon_basic_table[weapon_id]
        weapon_name = get_item_name(weapon_id, "CN")
        weapon_type = get_translation(
            weapon_type_int_to_translation_key[weapon_id], "CN"
        )
        return f"<bold>{weapon_name}（{weapon_basic['rarity']}★ {weapon_type}）</>"

    if non_trash_weapon_ids:
        # 只要有一个匹配武器未被拦截，就是宝藏

        # 输出所有匹配到且未被拦截的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in non_trash_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        return EvaluationResult(
            quality=EssenceQuality.TREASURE,
            log_message=f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器{weapons_description_str}{high_level_info}。",
            matched_weapons=non_trash_weapon_ids,
            is_high_level=is_high_level_treasure,
        )
    else:
        # 所有匹配到的武器都在 trash_weapon_ids 中

        # 输出所有匹配到的武器列表
        weapon_descriptions = [
            format_weapon_description(wid) for wid in matched_weapon_ids
        ]
        weapons_description_str = "、".join(weapon_descriptions)

        if is_high_level_treasure:
            return EvaluationResult(
                quality=EssenceQuality.TREASURE,
                log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。<yellow>即使它匹配的所有武器{weapons_description_str}均已被用户手动拦截。</>",
                matched_weapons=matched_weapon_ids,
                is_high_level=True,
            )
        else:
            return EvaluationResult(
                quality=EssenceQuality.TRASH,
                log_message=f"这个基质虽然匹配武器{weapons_description_str}，但匹配的所有武器均已被用户手动拦截，因此这个基质是<red><bold><underline>养成材料</></></>。",
                matched_weapons=matched_weapon_ids,
                is_high_level=False,
            )
