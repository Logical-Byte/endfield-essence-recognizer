"""
Recognition of delivery job rewards.
"""

import importlib.resources
from enum import StrEnum

from endfield_essence_recognizer.core.recognition.template_recognizer import (
    RecognitionProfile,
    TemplateDescriptor,
)


class DeliveryJobRewardLabel(StrEnum):
    """Labels for delivery job rewards."""

    WULING_DISPATCH_TICKET = "Wuling Dispatch Ticket"
    UNKNOWN = "Unknown"


def build_delivery_job_reward_profile() -> RecognitionProfile[DeliveryJobRewardLabel]:
    """
    Build the recognition profile for delivery job reward detection.
    """
    ticket_template = (
        importlib.resources.files("endfield_essence_recognizer")
        / "templates/screenshot/抢单报酬_武陵调度券.png"
    )
    templates = [
        TemplateDescriptor(
            path=ticket_template,
            label=DeliveryJobRewardLabel.WULING_DISPATCH_TICKET,
        ),
    ]
    return RecognitionProfile(
        templates=templates,
        high_threshold=0.8,
        low_threshold=0.8,
    )
