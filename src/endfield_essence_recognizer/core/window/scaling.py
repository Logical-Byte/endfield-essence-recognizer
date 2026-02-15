"""
Resolution scaling middleware.

Provides adapter classes that normalize arbitrary screen resolutions to a standard
logical resolution (default 1080p height), enabling resolution-independent recognition
and interaction logic.

The scaling layer sits between the raw window capture (physical) and the scanner engine
(logical), transparently converting images and coordinates in both directions.
"""

import cv2
from cv2.typing import MatLike

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import Region
from endfield_essence_recognizer.utils.log import logger

# Default logical height used as the normalization target.
DEFAULT_LOGICAL_HEIGHT = 1080


class ScalingImageSource(ImageSource):
    """
    An ImageSource adapter that scales captured images to a standard logical resolution.

    The scaling strategy is height-based: the image is resized so that its height
    equals ``logical_height`` (default 1080), while the width is scaled proportionally
    to preserve the original aspect ratio.

    After scaling, all ROI coordinates defined in the logical coordinate system can be
    applied directly to the scaled image.
    """

    def __init__(
        self,
        source: ImageSource,
        logical_height: int = DEFAULT_LOGICAL_HEIGHT,
    ) -> None:
        self._source = source
        self._logical_height = logical_height

        # Cache the physical size and compute scale factor once
        physical_width, physical_height = source.get_client_size()
        self._physical_width = physical_width
        self._physical_height = physical_height
        self._scale_factor = logical_height / physical_height
        self._logical_width = round(physical_width * self._scale_factor)

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
