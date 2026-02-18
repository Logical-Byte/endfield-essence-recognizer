import threading
from typing import Protocol, runtime_checkable

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Region


@runtime_checkable
class AutomationEngine(Protocol):
    """
    Protocol for automated task engines that operate on the target window.
    """

    def execute(self, stop_event: threading.Event) -> None:
        """
        Execute the automation loop.

        Args:
            stop_event: Event used to signal the engine to stop its operation.
        """
        ...


@runtime_checkable
class ImageSource(Protocol):
    """
    Protocol for objects that can provide images from a source (typically a window).
    """

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        """
        Take a screenshot of a specific region or the entire source.

        Args:
            relative_region: The region to capture, relative to the source's client area.
                             If None, captures the entire client area.

        Returns:
            The captured image as a MatLike (OpenCV BGR array).
        """
        ...

    def get_client_size(self) -> tuple[int, int]:
        """
        Get the dimensions of the source's client area.

        Returns:
            A tuple of (width, height).
        """
        ...


@runtime_checkable
class WindowActions(Protocol):
    """
    Protocol for performing interactive actions on a target window.
    """

    @property
    def target_exists(self) -> bool:
        """Whether the target window currently exists."""
        ...

    @property
    def target_is_active(self) -> bool:
        """Whether the target window is currently the foreground window."""
        ...

    def restore(self) -> bool:
        """
        Restore the window if it is minimized.

        Returns:
            True if the window was restored, False otherwise.
        """
        ...

    def activate(self) -> bool:
        """
        Activate the window (bring it to the foreground).

        Returns:
            True if the window was activated, False otherwise.
        """
        ...

    def show(self) -> bool:
        """
        Show the window if it is hidden.

        Returns:
            True if the window was shown, False otherwise.
        """
        ...

    def click(self, relative_x: int, relative_y: int) -> None:
        """
        Perform a left mouse click at the specified relative coordinates.

        Args:
            relative_x: X coordinate relative to the client area.
            relative_y: Y coordinate relative to the client area.
        """
        ...

    def wait(self, seconds: float) -> None:
        """
        Wait for a specified duration.

        Args:
            seconds: The number of seconds to wait.
        """
        ...

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
        ...


@runtime_checkable
class HotkeyHandler(Protocol):
    """
    Protocol for hotkey handler functions.

    The implementing function should accept a single string argument (the hotkey)
    and return None.
    """

    def __call__(self, key: str) -> None:
        """
        Handle a hotkey trigger.

        Args:
            key: The hotkey string that triggered the handler.
        """
        ...
