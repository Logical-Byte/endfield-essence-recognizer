import asyncio
import datetime
from pathlib import Path

import cv2

from endfield_essence_recognizer.core.layout.base import (
    ResolutionProfile,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.schemas.screenshot import (
    ImageFormat,
    ScreenshotSaveFormat,
)
from endfield_essence_recognizer.utils.image import (
    image_to_data_uri,
    mask_region,
    save_image,
)
from endfield_essence_recognizer.utils.log import logger


class ScreenshotService:
    """Service for taking and saving screenshots of the game window."""

    def __init__(self, window_manager: WindowManager):
        self._window_manager = window_manager

    async def capture_as_data_uri(
        self,
        width: int = 1920,
        height: int = 1080,
        format: ImageFormat = ImageFormat.JPG,  # noqa: A002
        quality: int = 75,
    ) -> str | None:
        """
        Captures the game window and returns it as a base64 encoded data URI.

        Args:
            width: The desired width of the image.
            height: The desired height of the image.
            format: The image format.
            quality: The quality of the encoded image (for lossy formats).

        Returns:
            A data URI string or None if the window is not active.
        """
        if not self._window_manager.target_is_active:
            return None

        # Capture screenshot
        image = self._window_manager.screenshot()
        # Resize to requested dimensions
        image = cv2.resize(image, (width, height))
        logger.debug("[ScreenshotService] Successfully captured and resized window.")

        return image_to_data_uri(image, fmt=format, quality=quality)

    async def capture_and_save(
        self,
        screenshot_dir: Path,
        resolution_profile: ResolutionProfile,
        should_focus: bool = True,
        post_process: bool = True,
        title: str = "Endfield",
        fmt: ScreenshotSaveFormat = ScreenshotSaveFormat.PNG,
    ) -> tuple[str, str]:
        """
        Takes a screenshot of the game window and saves it to the root directory.

        Args:
            resolution_profile: The resolution profile to determine the masking regions.
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
            if self._window_manager.show():
                await asyncio.sleep(0.2)
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
            mask_region(image, resolution_profile.MASK_ESSENCE_REGION_UID)
            mask_region(image, resolution_profile.MASK_ESSENCE_REGION_CURRENCY)

        # Generate filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        resolution = f"{width}x{height}"
        ext = f".{fmt.lower()}"
        file_name = f"{title}_{resolution}_{timestamp}{ext}"

        logger.debug("[ScreenshotService] Saving screenshot as {}", file_name)
        # Save to screenshots directory under root
        save_path = screenshot_dir / file_name
        save_image(image, save_path, ext=ext)

        return str(save_path), file_name
