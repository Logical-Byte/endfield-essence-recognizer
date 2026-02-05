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
from endfield_essence_recognizer.models.user_setting import Action, UserSetting


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
) -> list[ScannerAction]:
    """
    Decides what physical actions to perform based on the current state vs desired quality.

    Logic:
    - If locked but should be unlocked (based on Trash/Treasure settings), return CLICK_LOCK action with "Unlocked" message.
    - If unlocked but should be locked, return CLICK_LOCK action with "Locked" message.
    - If abandoned but should be kept, return CLICK_ABANDON with "Unabandoned" message.
    - If kept but should be abandoned, return CLICK_ABANDON with "Abandoned" message.

    Note:
    - Message should be in Chinese, and align with the current implementation for consistency.

    Args:
        data: Current state of the essence (locked?, observed?).
        evaluation: The judged quality (Treasure/Trash) from evaluate_essence.
        setting: User preferences for actions (e.g. treasure_action=LOCK).

    Returns:
        An ordered list of actions to apply to the game client sequentially.
    """
    actions: list[ScannerAction] = []

    # --- Lock Logic ---
    should_lock = False
    should_unlock = False

    if evaluation.quality == EssenceQuality.TREASURE:
        target_action = setting.treasure_action
    else:  # TRASH
        target_action = setting.trash_action

    if target_action == Action.LOCK:
        should_lock = True
    elif target_action in [Action.UNLOCK, Action.UNLOCK_AND_UNDEPRECATE]:
        should_unlock = True

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

    if target_action == Action.DEPRECATE:
        should_abandon = True
    elif target_action in [Action.UNDEPRECATE, Action.UNLOCK_AND_UNDEPRECATE]:
        should_unabandon = True

    if data.abandon_label == AbandonStatusLabel.NOT_ABANDONED and should_abandon:
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
