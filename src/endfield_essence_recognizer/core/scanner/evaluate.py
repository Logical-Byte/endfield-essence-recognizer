from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.user_setting import UserSetting


def evaluate_essence(
    data: EssenceData,
    setting: UserSetting,
    static_game_data: StaticGameData,
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
    stats = data.stats
    levels = data.levels

    # Check attribute levels: if high-level evaluation is enabled, record whether it is a high-level treasure
    is_high_level_treasure = False
    high_level_info = ""
    if setting.high_level_treasure_enabled:
        # The order of stats is [attribute, secondary, skill], corresponding to termType [0, 1, 2]
        thresholds = [
            setting.high_level_treasure_attribute_threshold,  # attribute threshold
            setting.high_level_treasure_secondary_threshold,  # secondary stat threshold
            setting.high_level_treasure_skill_threshold,  # skill stat threshold
        ]
        # Mapping for V2 StatType to threshold index
        type_to_index = {
            "ATTRIBUTE": 0,
            "SECONDARY": 1,
            "SKILL": 2,
        }
        for stat_id, level in zip(stats, levels, strict=True):
            if stat_id is not None and level is not None:
                stat = static_game_data.get_stat(stat_id)
                if stat is not None:
                    idx = type_to_index.get(stat.type)
                    if idx is not None:
                        threshold = thresholds[idx]
                        if level >= threshold:
                            is_high_level_treasure = True
                            high_level_info = (
                                f"（含高等级属性词条：{stat.name}+{level}）"
                            )
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
    matched_weapon_ids = set(
        static_game_data.find_weapons_by_stats(stats[0], stats[1], stats[2])
    )

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
        weapon = static_game_data.get_weapon(weapon_id)
        if not weapon:
            return f"<bold>{weapon_id}</>"

        weapon_type = static_game_data.get_weapon_type(weapon.weapon_type)
        type_name = weapon_type.name if weapon_type else "未知类型"

        return f"<bold>{weapon.name}（{weapon.rarity}★ {type_name}）</>"

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
