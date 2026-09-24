"""Layer 3：日志组装——根据分类结果和认领结果生成最终的 EvaluationResult。"""

from endfield_essence_recognizer.core.scanner.classifier import _custom_stat_display
from endfield_essence_recognizer.core.scanner.evaluate import _order_candidate_ids
from endfield_essence_recognizer.core.scanner.models import (
    ClaimResult,
    ClassificationResult,
    EssenceQuality,
    EvaluationResult,
    RejectReason,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.schemas.user_setting import UserSetting


def _format_weapon_description(
    weapon_id: str,
    setting: UserSetting,
    static_game_data: StaticGameData,
) -> str:
    """格式化武器描述。"""
    from endfield_essence_recognizer.schemas.profile import CUSTOM_ID_PREFIX

    if weapon_id.startswith(CUSTOM_ID_PREFIX):
        custom_display = _custom_stat_display(setting, weapon_id)
        return f"<fg #FF7100><bold>{custom_display}（自定义基质）</></>"
    weapon = static_game_data.get_weapon(weapon_id)
    if not weapon:
        return f"<bold>{weapon_id}</>"
    weapon_type = static_game_data.get_weapon_type(weapon.weapon_type)
    type_name = weapon_type.name if weapon_type else "未知类型"
    rarity_color = static_game_data.get_rarity_color(weapon.rarity)
    return (
        f"<fg {rarity_color}><bold>{weapon.name}（{weapon.rarity}★ {type_name}）</></>"
    )


def build_evaluation_result(
    classification: ClassificationResult,
    claim_result: ClaimResult,
    static_game_data: StaticGameData,
    setting: UserSetting,
    weapon_priority_order: list[str] | None = None,
) -> EvaluationResult:
    """根据分类结果和认领结果组装最终的 EvaluationResult（含 log_message）。"""
    quality = classification.quality

    # ── SKIP ──
    if quality == EssenceQuality.SKIP:
        if classification.stop_scan:
            return EvaluationResult(
                quality=EssenceQuality.SKIP,
                log_message="这个基质是<dim>非无瑕基质</>，已根据设置结束本次扫描。",
                stop_scan=True,
            )
        return EvaluationResult(
            quality=EssenceQuality.SKIP,
            log_message="这个基质是<dim>非无瑕基质</>，已根据设置跳过处理。",
        )

    # ── TRASH（分类阶段即判定为养成材料）──
    if quality == EssenceQuality.TRASH:
        return _build_trash_message(classification, static_game_data, setting)

    # ── TREASURE ──
    # 认领被拒绝 → 降级为养成材料
    if claim_result.reject_reason is not None:
        return _build_rejected_message(
            classification, claim_result, static_game_data, setting
        )

    # 认领成功（或未被拒绝的保留）→ 宝藏
    return _build_treasure_message(
        classification, claim_result, static_game_data, setting, weapon_priority_order
    )


def _build_trash_message(
    classification: ClassificationResult,
    static_game_data: StaticGameData,
    setting: UserSetting,
) -> EvaluationResult:
    """构建分类阶段即为养成材料的 log_message。"""
    # 非无瑕基质
    if not classification.is_high_level and classification.all_matched_weapon_ids:
        # 所有匹配武器被拦截
        weapons_desc = "、".join(
            _format_weapon_description(wid, setting, static_game_data)
            for wid in classification.all_matched_weapon_ids
        )
        return EvaluationResult(
            quality=EssenceQuality.TRASH,
            log_message=(
                f"这个基质虽然匹配武器{weapons_desc}，但匹配的所有武器均已被用户手动拦截，"
                f"因此这个基质是<red><bold><underline>养成材料</></></>。"
            ),
            matched_weapons=classification.all_matched_weapon_ids,
            matched_weapons_all_blocked=True,
            is_high_level=False,
        )

    # 不匹配任何武器
    return EvaluationResult(
        quality=EssenceQuality.TRASH,
        log_message="这个基质是<red><bold><underline>养成材料</></></>，它不匹配任何已实装武器。",
        is_high_level=False,
    )


def _build_rejected_message(
    classification: ClassificationResult,
    claim_result: ClaimResult,
    static_game_data: StaticGameData,
    setting: UserSetting,
) -> EvaluationResult:
    """构建认领被拒绝（降级为养成材料）的 log_message。"""
    reason = claim_result.reject_reason

    if reason == RejectReason.LIMIT:
        # 达到数量上限
        count = claim_result.current_count
        limit = setting.same_type_treasure_limit
        return EvaluationResult(
            quality=EssenceQuality.TRASH,
            log_message=(
                "这个基质是<red><bold><underline>养成材料</></></>，"
                f"因为同类型宝藏基质已扫描到 {count} 个，达到设置上限 {limit} 个。"
            ),
            matched_weapons=classification.matched_weapon_ids,
            matched_weapons_all_blocked=True,
            is_high_level=classification.is_high_level,
        )

    if reason == RejectReason.WORSE_LEVEL:
        return EvaluationResult(
            quality=EssenceQuality.TRASH,
            log_message=(
                "这个基质是<red><bold><underline>养成材料</></></>，"
                "因为它的等级低于已保存的最佳基质，不会被接收。"
            ),
            matched_weapons=classification.matched_weapon_ids,
            matched_weapons_all_blocked=True,
            is_high_level=classification.is_high_level,
        )

    if reason == RejectReason.NON_DOWNGRADE:
        return EvaluationResult(
            quality=EssenceQuality.TRASH,
            log_message=(
                "这个基质是<red><bold><underline>养成材料</></></>，"
                "因为它无法升级任何匹配武器的已有基质（不满足非降级原则）。"
            ),
            matched_weapons=classification.matched_weapon_ids,
            matched_weapons_all_blocked=True,
            is_high_level=classification.is_high_level,
        )

    # 未知拒绝原因（不应到达）
    return EvaluationResult(
        quality=EssenceQuality.TRASH,
        log_message="这个基质是<red><bold><underline>养成材料</></></>。",
        matched_weapons=classification.matched_weapon_ids,
        is_high_level=classification.is_high_level,
    )


def _build_treasure_message(
    classification: ClassificationResult,
    claim_result: ClaimResult,
    static_game_data: StaticGameData,
    setting: UserSetting,
    weapon_priority_order: list[str] | None = None,
) -> EvaluationResult:
    """构建宝藏基质的 log_message。"""
    high_level_info = classification.high_level_info
    matched_ids = classification.matched_weapon_ids

    # 自定义基质匹配
    if classification.custom_treasure_name:
        non_trash_ids = (
            matched_ids - set(setting.trash_weapon_ids) if matched_ids else set()
        )
        if non_trash_ids:
            weapon_descriptions = [
                _format_weapon_description(wid, setting, static_game_data)
                for wid in _order_candidate_ids(non_trash_ids, weapon_priority_order)
            ]
            weapons_str = "、".join(weapon_descriptions)
            return EvaluationResult(
                quality=EssenceQuality.TREASURE,
                log_message=f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器{weapons_str}{high_level_info}。",
                matched_weapons=non_trash_ids,
                matched_weapons_all_blocked=False,
                is_high_level=classification.is_high_level,
            )
        # 无候选武器
        return EvaluationResult(
            quality=EssenceQuality.TREASURE,
            log_message=(
                f"这个基质是<green><bold><underline>宝藏</></></>，"
                f"因为它符合自定义基质 <fg #FF7100><bold>{classification.custom_treasure_name}</></> 的条件{high_level_info}。"
            ),
            matched_weapons=set(),
            matched_weapons_all_blocked=True,
            is_high_level=classification.is_high_level,
        )

    # 无匹配武器但有高等级属性
    if not matched_ids:
        return EvaluationResult(
            quality=EssenceQuality.TREASURE,
            log_message=f"这个基质是<green><bold><underline>宝藏</></></>，因为它有高等级属性词条{high_level_info}。<dim>（但不匹配任何已实装武器）</>",
            is_high_level=True,
        )

    # 所有匹配武器被拦截但有高等级属性
    if classification.all_blocked:
        weapons_desc = "、".join(
            _format_weapon_description(wid, setting, static_game_data)
            for wid in classification.all_matched_weapon_ids
        )
        return EvaluationResult(
            quality=EssenceQuality.TREASURE,
            log_message=(
                f"这个基质是<green><bold><underline>宝藏</></></>，"
                f"因为它有高等级属性词条{high_level_info}。"
                f"<yellow>即使它匹配的所有武器{weapons_desc}均已被用户手动拦截。</>"
            ),
            matched_weapons=classification.all_matched_weapon_ids,
            matched_weapons_all_blocked=True,
            is_high_level=True,
        )

    # 正常宝藏：匹配武器
    weapon_descriptions = [
        _format_weapon_description(wid, setting, static_game_data)
        for wid in _order_candidate_ids(matched_ids, weapon_priority_order)
    ]
    weapons_str = "、".join(weapon_descriptions)
    return EvaluationResult(
        quality=EssenceQuality.TREASURE,
        log_message=f"这个基质是<green><bold><underline>宝藏</></></>，它完美契合武器{weapons_str}{high_level_info}。",
        matched_weapons=matched_ids,
        matched_weapons_all_blocked=False,
        is_high_level=classification.is_high_level,
    )
