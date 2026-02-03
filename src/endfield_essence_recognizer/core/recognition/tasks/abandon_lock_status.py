import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)


class AbandonStatusLabel(StrEnum):
    """Labels for weapon essence abandon status recognition."""

    ABANDONED = "已弃用"
    NOT_ABANDONED = "未弃用"
    MAYBE_ABANDONED = "不知道是否已弃用"


class LockStatusLabel(StrEnum):
    """Labels for weapon essence lock status recognition."""

    LOCKED = "已锁定"
    NOT_LOCKED = "未锁定"
    MAYBE_LOCKED = "不知道是否已锁定"


def build_abandon_status_profile() -> RecognitionProfile[AbandonStatusLabel]:
    """
    Build the recognition profile for abandon status icons.
    """
    templates_dir = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot"
    )
    templates = [
        TemplateDescriptor(
            path=templates_dir / "已弃用.png", label=AbandonStatusLabel.ABANDONED
        ),
        TemplateDescriptor(
            path=templates_dir / "未弃用.png", label=AbandonStatusLabel.NOT_ABANDONED
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.75,
        low_threshold=0.50,
    )


def build_lock_status_profile() -> RecognitionProfile[LockStatusLabel]:
    """
    Build the recognition profile for lock status icons.
    """
    templates_dir = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot"
    )
    templates = [
        TemplateDescriptor(
            path=templates_dir / "已锁定.png", label=LockStatusLabel.LOCKED
        ),
        TemplateDescriptor(
            path=templates_dir / "未锁定.png", label=LockStatusLabel.NOT_LOCKED
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.75,
        low_threshold=0.50,
    )
