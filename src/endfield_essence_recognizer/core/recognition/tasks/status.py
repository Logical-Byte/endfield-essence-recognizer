import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)


class StatusLabel(StrEnum):
    """Labels for weapon essence status recognition."""

    ABANDONED = "已弃用"
    NOT_ABANDONED = "未弃用"
    LOCKED = "已锁定"
    UNLOCKED = "未锁定"


def build_status_profile() -> RecognitionProfile[StatusLabel]:
    """
    Build the recognition profile for status icons (abandoned, locked, etc.).
    """
    templates_dir = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot"
    )

    templates: list[TemplateDescriptor[StatusLabel]] = []
    for label in StatusLabel:
        template_path = templates_dir / f"{label.value}.png"
        templates.append(TemplateDescriptor(path=template_path, label=label))

    return RecognitionProfile(
        templates=templates,
        high_threshold=0.75,
        low_threshold=0.50,
    )
