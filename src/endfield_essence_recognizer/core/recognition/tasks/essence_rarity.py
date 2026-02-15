from enum import StrEnum

from endfield_essence_recognizer.core.recognition.color_recognizer import (
    ColorDescriptor,
    ColorRecognitionProfile,
)


class RarityLabel(StrEnum):
    """Labels for weapon essence rarity recognition."""

    FIVE = "5"
    FOUR = "4"
    OTHER = "other"


def build_rarity_profile() -> ColorRecognitionProfile[RarityLabel]:
    """
    Build the recognition profile for weapon essence rarity based on color.
    """
    return ColorRecognitionProfile(
        descriptors=[
            ColorDescriptor(
                label=RarityLabel.FIVE,
                bgr=(3, 186, 255),  # RGB 255, 186, 3
            ),
            ColorDescriptor(
                label=RarityLabel.FOUR,
                bgr=(250, 82, 148),  # RGB 148, 82, 250
            ),
        ],
        hue_threshold_deg=15.0,
        min_saturation=50,
    )
