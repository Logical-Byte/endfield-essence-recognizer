from dataclasses import dataclass

import cv2
import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.utils.log import logger


def bgr_to_hsv(bgr: tuple[int, int, int] | np.ndarray) -> tuple[int, int, int]:
    """Converts a BGR color to HSV using OpenCV."""
    if isinstance(bgr, tuple):
        bgr_pixel = np.array([[list(bgr)]], dtype=np.uint8)
    else:
        bgr_pixel = np.uint8([[bgr]])  # type: ignore
    hsv_pixel = cv2.cvtColor(bgr_pixel, cv2.COLOR_BGR2HSV)[0][0]  # type: ignore
    return int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2])


def hsv_to_hue_deg(hsv_h: int) -> float:
    """Converts OpenCV's Hue [0, 180] to degrees [0, 360]."""
    return float(hsv_h) * 2


@dataclass(frozen=True)
class ColorDescriptor[LabelT]:
    """Describes a target color and its associated label."""

    label: LabelT
    """The label associated with this color."""
    bgr: tuple[int, int, int]
    """The target color in BGR format."""


@dataclass
class HueRecognitionProfile[LabelT]:
    """Configuration for HueRecognizer."""

    descriptors: list[ColorDescriptor[LabelT]]
    """List of color descriptors to recognize."""
    hue_threshold_deg: float = 15.0
    """Maximum hue angular distance for matching (in degrees, 0 to 180)."""
    min_saturation: int = 50
    """Minimum saturation (0-255) to consider a color valid."""


class HueRecognizer[LabelT]:
    """
    Recognizes a state based on the dominant color of an ROI using Hue similarity.
    """

    def __init__(self, name: str, profile: HueRecognitionProfile[LabelT]) -> None:
        self.name = name
        self.profile = profile
        self._target_hues: list[tuple[LabelT, float]] = []

        self._validate_and_initialize()

    def __str__(self) -> str:
        return f"[{self.name}]"

    def _validate_and_initialize(self) -> None:
        """Validates the profile and initializes target hues."""
        min_dist_deg = 2 * self.profile.hue_threshold_deg

        for desc in self.profile.descriptors:
            # Convert target BGR to HSV
            h, s, _ = bgr_to_hsv(desc.bgr)

            if s < self.profile.min_saturation:
                logger.warning(
                    f"{self} Descriptor '{desc.label}' color {desc.bgr} has low saturation ({s} < {self.profile.min_saturation})"
                )

            hue_deg = hsv_to_hue_deg(h)
            self._target_hues.append((desc.label, hue_deg))

        # Check for overlapping recognition zones
        n = len(self._target_hues)
        for i in range(n):
            for j in range(i + 1, n):
                label1, hue1 = self._target_hues[i]
                label2, hue2 = self._target_hues[j]

                # Circular distance
                dist = abs(hue1 - hue2)
                if dist > 180:
                    dist = 360 - dist

                if dist < min_dist_deg:
                    logger.warning(
                        f"{self} Target colors for '{label1}' ({hue1:.1f}°) and '{label2}' ({hue2:.1f}°) "
                        f"are too close (dist={dist:.1f}° < min={min_dist_deg:.1f}°)"
                    )

    def recognize_roi(self, roi_image: MatLike) -> tuple[LabelT | None, float]:
        """
        Recognizes the color in the ROI.
        Returns (Label, SimilarityScore).
        """
        if not self._target_hues or roi_image.size == 0:
            return None, 0.0

        # Calculate average color
        avg_bgr = np.mean(roi_image, axis=(0, 1))  # type: ignore
        h, s, _ = bgr_to_hsv(avg_bgr)

        if s < self.profile.min_saturation:
            logger.trace(
                f"{self} ROI saturation too low ({s} < {self.profile.min_saturation})"
            )
            return None, 0.0

        roi_hue_deg = hsv_to_hue_deg(h)
        best_label: LabelT | None = None
        best_dist = 360.0

        for label, target_hue in self._target_hues:
            # Angular distance
            dist = abs(roi_hue_deg - target_hue)
            if dist > 180:
                dist = 360 - dist

            if dist < best_dist:
                best_dist = dist
                best_label = label

        # Convert distance to a "score" where 1.0 is perfect and 0.0 is worst (180 deg)
        score = 1.0 - (best_dist / 180.0)

        if best_dist <= self.profile.hue_threshold_deg:
            return best_label, score

        return None, score

    def recognize_roi_fallback(
        self, roi_image: MatLike, fallback_label: LabelT
    ) -> tuple[LabelT, float]:
        """Recognizes the color, returning a fallback label if no match is found."""
        label, score = self.recognize_roi(roi_image)
        if label is None:
            return fallback_label, score
        return label, score
