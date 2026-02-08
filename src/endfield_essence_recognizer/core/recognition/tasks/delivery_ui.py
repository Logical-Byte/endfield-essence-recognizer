"""
Detect delivery-related UI scenes.
"""

import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.base import (
    RecognitionProfile,
    TemplateDescriptor,
)


class DeliverySceneLabel(StrEnum):
    """Labels for different delivery UI scenes."""

    LIST_OF_DELIVERY_JOBS = "List of Delivery Jobs"
    UNKNOWN = "Unknown"


def build_delivery_scene_profile() -> RecognitionProfile[DeliverySceneLabel]:
    """
    Build the recognition profile for delivery scene detection.
    """
    list_of_jobs_template = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot/运送委托列表_已激活.png"
    )
    templates = [
        TemplateDescriptor(
            path=list_of_jobs_template,
            label=DeliverySceneLabel.LIST_OF_DELIVERY_JOBS,
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.8,
        low_threshold=0.8,
    )
