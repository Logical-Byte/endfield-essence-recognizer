from typing import Protocol, runtime_checkable

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Region


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
