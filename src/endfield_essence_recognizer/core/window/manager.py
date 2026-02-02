from collections.abc import Sequence

import pygetwindow
from cv2.typing import MatLike

from endfield_essence_recognizer.core.window.windows_utils import (
    click_on_window,
    get_client_size,
    get_support_window,
    screenshot_window,
)
from endfield_essence_recognizer.utils.image import Scope


class WindowManager:
    """
    A proxy to interact with the target application window.

    Encapsulates all window-related operations (finding, screenshotting, clicking).
    Hides third-party library objects from the consumer.

    We cannot (and nobody can) guarantee atomicity of operations on the window, since user may move,
    resize, minimize the window at any time. For our use case, this is acceptable.
    """

    def __init__(self, supported_titles: Sequence[str]):
        self._supported_titles = supported_titles
        self._window: pygetwindow.Window | None = None

    def _get_window(self) -> pygetwindow.Window | None:
        """Internal helper to get the current target window with caching."""
        if self._window is None:
            self._window = get_support_window(self._supported_titles)
        return self._window

    def clear(self) -> None:
        """Clear the cached window instance."""
        self._window = None

    @property
    def target_exists(self) -> bool:
        """Check if any supported window is currently open."""
        return self._get_window() is not None

    @property
    def target_is_active(self) -> bool:
        """Check if the supported window is the foreground window."""
        window = self._get_window()
        return window.isActive if window else False

    def restore(self) -> bool:
        """
        Restore the window if it is minimized.
        Returns True if an operation was performed, False otherwise.
        """
        window = self._get_window()
        if window and window.isMinimized:
            window.restore()
            return True
        return False

    def activate(self) -> bool:
        """
        Activate the window if it is not active.
        Returns True if an operation was performed, False otherwise.
        """
        window = self._get_window()
        if window and not window.isActive:
            window.activate()
            return True
        return False

    def get_client_size(self) -> tuple[int, int]:
        """Return the (width, height) of the window's client area."""
        window = self._get_window()
        if not window:
            raise RuntimeError(
                f"No window found matching titles: {self._supported_titles}"
            )
        return get_client_size(window)

    def screenshot(self, relative_region: Scope | None = None) -> MatLike:
        """
        Take a screenshot of the window's client area.
        Returns a BGR numpy array compatible with OpenCV.
        """
        window = self._get_window()
        if not window:
            raise RuntimeError(
                f"No window found matching titles: {self._supported_titles}"
            )
        return screenshot_window(window, relative_region)

    def click(self, relative_x: int, relative_y: int) -> None:
        """Perform a mouse click at the relative coordinates within the client area."""
        window = self._get_window()
        if not window:
            raise RuntimeError(
                f"No window found matching titles: {self._supported_titles}"
            )
        click_on_window(window, relative_x, relative_y)
