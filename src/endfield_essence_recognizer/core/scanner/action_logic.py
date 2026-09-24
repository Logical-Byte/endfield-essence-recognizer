from dataclasses import dataclass
from enum import Enum, auto

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.game_data.models.v2 import StatType
from endfield_essence_recognizer.schemas.user_setting import Action, UserSetting


def _is_missing_stats(data: EssenceData) -> bool:
    """检查基质是否缺少任意一项词条（基础属性、附加属性、技能属性）。"""
    type_to_stat: dict[StatType, str | None] = {}
    for stat_id, stat_type in zip(data.stats, data.stat_types, strict=True):
        if (
            stat_type is not None
            and stat_id is not None
            and stat_type not in type_to_stat
        ):
            type_to_stat[stat_type] = stat_id

    has_attribute = StatType.ATTRIBUTE in type_to_stat
    has_secondary = StatType.SECONDARY in type_to_stat
    has_skill = StatType.SKILL in type_to_stat

    return not (has_attribute and has_secondary and has_skill)


class ActionType(Enum):
    CLICK_LOCK = auto()
    CLICK_ABANDON = auto()


@dataclass
class ScannerAction:
    """Represents a physical action to take and the feedback to give."""

    type: ActionType
    log_message: str


def decide_actions(
    data: EssenceData,
    evaluation: EvaluationResult,
    setting: UserSetting,
    target_action: Action | None = None,
) -> list[ScannerAction]:
    """
    Decides what physical actions to perform based on the current state vs desired quality.

    Logic:
    - If locked but should be unlocked (based on Trash/Treasure settings), return CLICK_LOCK action with a Chinese feedback message indicating it was unlocked.
    - If unlocked but should be locked, return CLICK_LOCK action with a Chinese feedback message indicating it was locked.
    - If abandoned but should be kept, return CLICK_ABANDON with a Chinese feedback message indicating abandonment was cancelled.
    - If kept but should be abandoned, return CLICK_ABANDON with a Chinese feedback message indicating it was marked as abandoned.

    Note:
    - Messages are localized (Chinese), and the exact text is implementation-specific but should align with the current implementation for consistency.

    Args:
        data: Current state of the essence (locked?, observed?).
        evaluation: The judged quality (Treasure/Trash) from evaluate_essence.
        setting: User preferences for actions (e.g. treasure_action=LOCK).
        target_action: 覆盖目标操作（冗余清理传入 setting.redundant_action）；
            None 时按 quality 取 treasure_action / trash_action。

    Returns:
        An ordered list of actions to apply to the game client sequentially.
    """
    if evaluation.quality == EssenceQuality.SKIP:
        return []

    actions: list[ScannerAction] = []

    if target_action is None:
        target_action = (
            setting.treasure_action
            if evaluation.quality == EssenceQuality.TREASURE
            else setting.trash_action
        )

    # --- Lock Logic ---
    should_lock = False
    should_unlock = False

    if target_action == Action.LOCK:
        should_lock = True
    elif target_action in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]:
        should_unlock = True
    elif (
        target_action == Action.LOCK_IF_NOT_DEPRECATED
        and data.abandon_label == AbandonStatusLabel.NOT_ABANDONED
    ):
        should_lock = True

    if data.lock_label == LockStatusLabel.NOT_LOCKED and should_lock:
        actions.append(
            ScannerAction(
                type=ActionType.CLICK_LOCK,
                log_message="给你自动锁上了，记得保管好哦！(*/ω＼*)",
            )
        )
    elif data.lock_label == LockStatusLabel.LOCKED and should_unlock:
        actions.append(
            ScannerAction(
                type=ActionType.CLICK_LOCK, log_message="给你自动解锁了！ヾ(≧▽≦*)o"
            )
        )

    # --- Abandon Logic ---
    should_abandon = False
    should_unabandon = False
    is_missing_stats_action = False

    if target_action == Action.DEPRECATE:
        should_abandon = True
    elif target_action in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]:
        should_unabandon = True
    elif (
        target_action == Action.DEPRECATE_IF_NOT_LOCKED
        and data.lock_label == LockStatusLabel.NOT_LOCKED
    ):
        should_abandon = True
    elif target_action == Action.DEPRECATE_IF_MISSING_STATS and _is_missing_stats(data):
        should_abandon = True
        is_missing_stats_action = True

    if data.abandon_label == AbandonStatusLabel.NOT_ABANDONED and should_abandon:
        if is_missing_stats_action:
            actions.append(
                ScannerAction(
                    type=ActionType.CLICK_ABANDON,
                    log_message="因为缺少词条，给你自动标记为弃用了！(￣︶￣)>",
                )
            )
        else:
            actions.append(
                ScannerAction(
                    type=ActionType.CLICK_ABANDON,
                    log_message="给你自动标记为弃用了！(￣︶￣)>",
                )
            )
    elif data.abandon_label == AbandonStatusLabel.ABANDONED and should_unabandon:
        actions.append(
            ScannerAction(
                type=ActionType.CLICK_ABANDON,
                log_message="给你自动取消弃用啦！(＾Ｕ＾)ノ~ＹＯ",
            )
        )

    return actions
