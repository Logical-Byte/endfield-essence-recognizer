import datetime

from endfield_essence_recognizer.core.path import get_root_dir
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.utils.image import save_image


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
            self._window_manager.activate()

        # Capture screenshot
        image = self._window_manager.screenshot()
        height, width = image.shape[:2]

        if post_process:
            # TODO: Implementation of post_process logic (masking bottom-left corner)
            pass

        # Generate filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        resolution = f"{width}x{height}"
        ext = f".{fmt.lower()}"
        file_name = f"{title}_{resolution}_{timestamp}{ext}"

        # Save to root directory
        save_path = get_root_dir() / file_name
        save_image(image, save_path, ext=ext)

        return str(save_path), file_name
