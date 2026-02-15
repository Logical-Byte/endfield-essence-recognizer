"""
Resolution scaling middleware.

Provides adapter classes that normalize arbitrary screen resolutions to a standard
logical resolution, enabling resolution-independent recognition and interaction logic.

Scaling strategy:
- Aspect ratio >= 16:9 (wide): scale by height to 1080, width >= 1920
- Aspect ratio < 16:9 (narrow): scale by width to 1920, height > 1080

This ensures the right-side attribute panel always maps to the same X coordinates
as the 1080p reference layout.

The scaling layer sits between the raw window capture (physical) and the scanner engine
(logical), transparently converting images and coordinates in both directions.
"""

import cv2
from cv2.typing import MatLike

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import Region
from endfield_essence_recognizer.utils.log import logger

# Reference resolution (16:9 baseline).
REF_WIDTH = 1920
REF_HEIGHT = 1080
REF_RATIO = REF_WIDTH / REF_HEIGHT


def compute_logical_size(
    physical_width: int, physical_height: int
) -> tuple[int, int, float]:
    """
    Compute the logical size and scale factor for a given physical resolution.

    Returns:
        (logical_width, logical_height, scale_factor)
    """
    ratio = physical_width / physical_height
    if ratio >= REF_RATIO:
        # Wide or standard: scale by height
        scale = REF_HEIGHT / physical_height
    else:
        # Narrow: scale by width
        scale = REF_WIDTH / physical_width
    return round(physical_width * scale), round(physical_height * scale), scale


class ScalingImageSource(ImageSource):
    """
    An ImageSource adapter that scales captured images to a standard logical resolution.

    Scaling strategy adapts to the aspect ratio:
    - Wide (>= 16:9): height fixed at 1080, width >= 1920
    - Narrow (< 16:9): width fixed at 1920, height > 1080

    After scaling, all ROI coordinates defined in the logical coordinate system can be
    applied directly to the scaled image.
    """

    def __init__(self, source: ImageSource) -> None:
        self._source = source

        # Cache the physical size and compute scale factor once
        physical_width, physical_height = source.get_client_size()
        self._physical_width = physical_width
        self._physical_height = physical_height
        self._logical_width, self._logical_height, self._scale_factor = (
            compute_logical_size(physical_width, physical_height)
        )

        logger.info(
            f"ScalingImageSource: "
            f"physical={physical_width}x{physical_height} -> "
            f"logical={self._logical_width}x{self._logical_height} "
            f"(scale={self._scale_factor:.4f})"
        )

    @property
    def scale_factor(self) -> float:
        """The ratio of logical size to physical size (logical / physical)."""
        return self._scale_factor

    @property
    def logical_size(self) -> tuple[int, int]:
        """The logical (width, height) after scaling."""
        return self._logical_width, self._logical_height

    @property
    def physical_size(self) -> tuple[int, int]:
        """The original physical (width, height)."""
        return self._physical_width, self._physical_height

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        """
        Capture a screenshot, scale it to the logical resolution, then optionally
        crop to the specified region.

        Args:
            relative_region: Region in logical coordinates to crop from the
                             scaled image. If None, returns the full scaled image.

        Returns:
            The scaled (and optionally cropped) image as a BGR MatLike.
        """
        full_physical = self._source.screenshot()

        scaled = cv2.resize(
            full_physical,
            (self._logical_width, self._logical_height),
            interpolation=cv2.INTER_LINEAR,
        )

        if relative_region is None:
            return scaled

        p0, p1 = relative_region.p0, relative_region.p1
        return scaled[p0.y : p1.y, p0.x : p1.x]

    def get_client_size(self) -> tuple[int, int]:
        """Return the logical client size (after scaling)."""
        return self._logical_width, self._logical_height


class ScalingWindowActions(WindowActions):
    """
    A WindowActions adapter that maps logical coordinates back to physical coordinates.

    When the scanner engine issues a click at logical position (x, y), this adapter
    converts it to the corresponding physical screen position before delegating to
    the underlying WindowActions implementation.
    """

    def __init__(
        self,
        actions: WindowActions,
        scaling_source: ScalingImageSource,
    ) -> None:
        self._actions = actions
        self._scaling_source = scaling_source

    @property
    def target_exists(self) -> bool:
        return self._actions.target_exists

    @property
    def target_is_active(self) -> bool:
        return self._actions.target_is_active

    def restore(self) -> bool:
        return self._actions.restore()

    def activate(self) -> bool:
        return self._actions.activate()

    def show(self) -> bool:
        return self._actions.show()

    def click(self, relative_x: int, relative_y: int) -> None:
        """
        Perform a click at logical coordinates, mapped back to physical coordinates.
        """
        scale_factor = self._scaling_source.scale_factor
        physical_x = round(relative_x / scale_factor)
        physical_y = round(relative_y / scale_factor)
        self._actions.click(physical_x, physical_y)

    def wait(self, seconds: float) -> None:
        self._actions.wait(seconds)
