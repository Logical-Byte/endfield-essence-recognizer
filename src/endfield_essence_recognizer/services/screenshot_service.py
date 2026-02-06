import asyncio
import datetime

from endfield_essence_recognizer.core.layout.base import Point, Region
from endfield_essence_recognizer.core.path import get_root_dir
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.utils.image import mask_region, save_image
from endfield_essence_recognizer.utils.log import logger


class ScreenshotService:
    """Service for taking and saving screenshots of the game window."""

    def __init__(self, window_manager: WindowManager):
        self._window_manager = window_manager

    async def capture_and_save(
        self,
        should_focus: bool = True,
        post_process: bool = True,
        title: str = "Endfield",
        fmt: str = "png",
    ) -> tuple[str, str]:
        """
        Takes a screenshot of the game window and saves it to the root directory.

        Args:
            should_focus: Whether to focus the game window before taking the screenshot.
            post_process: Whether to apply post-processing (e.g., masking privacy info).
            title: The title prefix for the filename.
            fmt: The file format (e.g., "png", "jpg").

        Returns:
            A tuple of (full_file_path, file_name).
        """
        if not self._window_manager.target_exists:
            raise RuntimeError("Game window not found.")

        if should_focus:
            logger.debug(
                "[ScreenshotService] Activating game window before screenshot."
            )
            if self._window_manager.restore():
                await asyncio.sleep(0.2)
            if self._window_manager.activate():
                await asyncio.sleep(0.2)

        # Capture screenshot
        logger.debug("[ScreenshotService] Capturing screenshot of the game window.")
        image = self._window_manager.screenshot()
        height, width = image.shape[:2]
        logger.debug("[ScreenshotService] Resolution: {} x {}", width, height)

        if post_process:
            logger.debug(
                "[ScreenshotService] Applying post-processing to the screenshot."
            )
            # uid area to mask: (0-270, 1040-1080) for 1080p
            # currency area to mask: 1340,20 - 1810,70
            # We hardcode this for now as requested.
            uid_mask_region = Region(Point(0, 1040), Point(270, 1080))
            currency_mask_region = Region(Point(1340, 20), Point(1810, 70))

            mask_region(image, uid_mask_region)
            mask_region(image, currency_mask_region)

        # Generate filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        resolution = f"{width}x{height}"
        ext = f".{fmt.lower()}"
        file_name = f"{title}_{resolution}_{timestamp}{ext}"

        logger.debug("[ScreenshotService] Saving screenshot as {}", file_name)
        # Save to screenshots directory under root
        save_path = get_root_dir() / "screenshots" / file_name
        save_image(image, save_path, ext=ext)

        return str(save_path), file_name
