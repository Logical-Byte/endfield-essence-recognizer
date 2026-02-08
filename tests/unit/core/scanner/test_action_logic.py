import pytest

from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    LockStatusLabel,
)
from endfield_essence_recognizer.core.scanner.action_logic import (
    ActionType,
    decide_actions,
)
from endfield_essence_recognizer.core.scanner.models import (
    EssenceData,
    EssenceQuality,
    EvaluationResult,
)
from endfield_essence_recognizer.models.user_setting import Action, UserSetting


@pytest.fixture
def default_data():
    return EssenceData(
        stats=[],
        levels=[],
        abandon_label=AbandonStatusLabel.NOT_ABANDONED,
        lock_label=LockStatusLabel.NOT_LOCKED,
    )


@pytest.fixture
def default_eval():
    return EvaluationResult(quality=EssenceQuality.TRASH, log_message="Trash")


@pytest.fixture
def default_settings():
    return UserSetting()


def test_no_action_needed(default_data, default_eval, default_settings):
    """
    Test that no action is generated when the current state matches the desired state.

    Condition:
    - Item is judged as TRASH.
    - User setting for TRASH is default (KEEP).
    - Result: No action.
    """
    # Trash, Default is KEEP/KEEP. No action.
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 0


def test_trace_lock(default_data, default_eval, default_settings):
    """
    Test that a LOCK action is generated when a TREASURE item is currently UNLOCKED.

    Condition:
    - Item is judged as TREASURE.
    - User setting for TREASURE is LOCK.
    - Current state is NOT_LOCKED.
    - Result: CLICK_LOCK action.
    """
    # Treasure -> Lock
    default_eval.quality = EssenceQuality.TREASURE
    default_settings.treasure_action = Action.LOCK

    # Currently unlocked
    default_data.lock_label = LockStatusLabel.NOT_LOCKED

    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 1
    assert actions[0].type == ActionType.CLICK_LOCK
    assert "锁" in actions[0].log_message


def test_trash_deprecate(default_data, default_eval, default_settings):
    """
    Test that an ABANDON action is generated when a TRASH item is currently NOT ABANDONED.

    Condition:
    - Item is judged as TRASH.
    - User setting for TRASH is DEPRECATE (Abandon).
    - Current state is NOT_ABANDONED.
    - Result: CLICK_ABANDON action.
    """
    # Trash -> Deprecate
    default_eval.quality = EssenceQuality.TRASH
    default_settings.trash_action = Action.DEPRECATE

    # Currently NOT abandoned
    default_data.abandon_label = AbandonStatusLabel.NOT_ABANDONED

    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 1
    assert actions[0].type == ActionType.CLICK_ABANDON
    assert "弃用" in actions[0].log_message


def test_mixed_actions_unlock_undeprecate(default_data, default_eval, default_settings):
    """
    Test that multiple actions are valid and returned when state is completely opposite to desired.

    Condition:
    - Item is judged as TREASURE.
    - User setting for TREASURE is UNLOCK_AND_UNDEPRECATE.
    - Current state is LOCKED and ABANDONED.
    - Result: CLICK_LOCK (to unlock) AND CLICK_ABANDON (to undeprecate).
    """
    # Treasure -> Unlock & Undeprecate
    default_eval.quality = EssenceQuality.TREASURE
    default_settings.treasure_action = Action.UNLOCK_AND_UNDEPRECATE

    # Currently Locked AND Abandoned
    default_data.lock_label = LockStatusLabel.LOCKED
    default_data.abandon_label = AbandonStatusLabel.ABANDONED

    actions = decide_actions(default_data, default_eval, default_settings)

    # Should perform both
    assert len(actions) == 2
    types = [a.type for a in actions]
    assert ActionType.CLICK_LOCK in types  # To unlock
    assert ActionType.CLICK_ABANDON in types  # To undeprecate


def test_deprecate_if_not_locked(default_data, default_eval, default_settings):
    """
    Test DEPRECATE_IF_NOT_LOCKED logic.
    """
    default_eval.quality = EssenceQuality.TRASH
    default_settings.trash_action = Action.DEPRECATE_IF_NOT_LOCKED

    # Case 1: Unlocked -> Should deprecate
    default_data.lock_label = LockStatusLabel.NOT_LOCKED
    default_data.abandon_label = AbandonStatusLabel.NOT_ABANDONED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 1
    assert actions[0].type == ActionType.CLICK_ABANDON

    # Case 2: Locked -> Should NOT deprecate
    default_data.lock_label = LockStatusLabel.LOCKED
    default_data.abandon_label = AbandonStatusLabel.NOT_ABANDONED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 0

    # Case 3: Unlocked but ALREADY abandoned -> Should NOT deprecate (no action needed)
    default_data.lock_label = LockStatusLabel.NOT_LOCKED
    default_data.abandon_label = AbandonStatusLabel.ABANDONED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 0


def test_lock_if_not_deprecated(default_data, default_eval, default_settings):
    """
    Test LOCK_IF_NOT_DEPRECATED logic.
    """
    default_eval.quality = EssenceQuality.TREASURE
    default_settings.treasure_action = Action.LOCK_IF_NOT_DEPRECATED

    # Case 1: Not abandoned -> Should lock
    default_data.abandon_label = AbandonStatusLabel.NOT_ABANDONED
    default_data.lock_label = LockStatusLabel.NOT_LOCKED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 1
    assert actions[0].type == ActionType.CLICK_LOCK

    # Case 2: Abandoned -> Should NOT lock
    default_data.abandon_label = AbandonStatusLabel.ABANDONED
    default_data.lock_label = LockStatusLabel.NOT_LOCKED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 0

    # Case 3: Not abandoned but ALREADY locked -> Should NOT lock (no action needed)
    default_data.abandon_label = AbandonStatusLabel.NOT_ABANDONED
    default_data.lock_label = LockStatusLabel.LOCKED
    actions = decide_actions(default_data, default_eval, default_settings)
    assert len(actions) == 0
