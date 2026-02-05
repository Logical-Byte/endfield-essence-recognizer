"""
Detect which UI scene we are currently in.
"""

import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)


class UISceneLabel(StrEnum):
    """Labels for different UI scenes."""

    ESSENCE_UI = "Essence UI"
    LIST_OF_DELIVERY_JOBS = "List of Delivery Jobs"
    UNKNOWN = "Unknown"


def build_ui_scene_profile() -> RecognitionProfile[UISceneLabel]:
    """
    Build the recognition profile for UI scene detection.
    """
    essence_ui_template = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot/武器基质.png"
    )
    list_of_delivery_jobs_template = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot/运送委托列表_已激活.png"
    )
    templates = [
        TemplateDescriptor(
            path=essence_ui_template,
            label=UISceneLabel.ESSENCE_UI,
        ),
        TemplateDescriptor(
            path=list_of_delivery_jobs_template,
            label=UISceneLabel.LIST_OF_DELIVERY_JOBS,
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.8,
        low_threshold=0.8,
    )
