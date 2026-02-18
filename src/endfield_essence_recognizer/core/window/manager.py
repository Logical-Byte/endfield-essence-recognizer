from collections.abc import Sequence

import pygetwindow
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Region
from endfield_essence_recognizer.core.window.windows_utils import (
    click_on_window,
    drag_on_window,
    get_client_size,
    get_support_window,
    screenshot_window,
)
from endfield_essence_recognizer.exceptions import WindowNotFoundError


class WindowManager:
    """
    A proxy to interact with the target application window.

    Encapsulates all window-related operations (finding, screenshotting, clicking).
    Hides third-party library objects from the consumer.

    We cannot (and nobody can) guarantee atomicity of operations on the window, since user may move,
    resize, minimize the window at any time. For our use case, this is acceptable.
    """

    def __init__(self, supported_titles: Sequence[str]):
        self._supported_titles = list(supported_titles)
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
    def supported_titles(self) -> list[str]:
        """Get the list of supported window titles."""
        return self._supported_titles

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
        Restore the window to normal size if it is minimized / maximized.
        Returns True if an operation was performed, False otherwise.
        """
        window = self._get_window()
        if window is not None and (window.isMinimized or window.isMaximized):
            window.restore()
            return True
        return False

    def show(self) -> bool:
        """
        Show the window if it is not visible.
        Returns True if an operation was performed, False otherwise.
        """
        window = self._get_window()
        if window and not window.visible:
            window.show()
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
        if window is None:
            raise WindowNotFoundError(self._supported_titles)
        return get_client_size(window)

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        """
        Take a screenshot of the window's client area.
        Returns a BGR numpy array compatible with OpenCV.
        """
        window = self._get_window()
        if window is None:
            raise WindowNotFoundError(self._supported_titles)
        return screenshot_window(window, relative_region)

    def click(self, relative_x: int, relative_y: int) -> None:
        """Perform a mouse click at the relative coordinates within the client area."""
        window = self._get_window()
        if window is None:
            raise WindowNotFoundError(self._supported_titles)
        click_on_window(window, relative_x, relative_y)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
        hold_time: float = 0.5,
    ) -> None:
        """
        Perform a mouse drag operation from start to end coordinates.

        Args:
            start_x: Starting X coordinate relative to the client area.
            start_y: Starting Y coordinate relative to the client area.
            end_x: Ending X coordinate relative to the client area.
            end_y: Ending Y coordinate relative to the client area.
            duration: Duration of the drag operation in seconds.
            hold_time: Time to hold the mouse button after reaching the end position.
        """
        window = self._get_window()
        if window is None:
            raise WindowNotFoundError(self._supported_titles)
        drag_on_window(window, start_x, start_y, end_x, end_y, duration, hold_time)
