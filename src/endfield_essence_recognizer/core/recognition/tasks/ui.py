"""
Detect which UI scene we are currently in.
"""

import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.template_recognizer import (
    RecognitionProfile,
    TemplateDescriptor,
)


class UISceneLabel(StrEnum):
    """Labels for different UI scenes."""

    ESSENCE_UI = "Essence UI"
    UNKNOWN = "Unknown"


def build_ui_scene_profile() -> RecognitionProfile[UISceneLabel]:
    """
    Build the recognition profile for UI scene detection.
    """
    essence_ui_template = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot/武器基质.png"
    )
    templates = [
        TemplateDescriptor(
            path=essence_ui_template,
            label=UISceneLabel.ESSENCE_UI,
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.8,
        low_threshold=0.8,
    )
