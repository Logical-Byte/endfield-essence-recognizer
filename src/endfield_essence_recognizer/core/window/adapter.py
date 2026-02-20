import time
from collections.abc import Callable

from cv2.typing import MatLike

from endfield_essence_recognizer.core.interfaces import ImageSource, WindowActions
from endfield_essence_recognizer.core.layout.base import Region
from endfield_essence_recognizer.core.window.manager import WindowManager


class WindowActionsAdapter(WindowActions, ImageSource):
    """
    Adapter that combines WindowManager with a wait (sleep) capability.
    This fulfills both WindowActions and ImageSource protocols for the ScannerEngine.
    """

    def __init__(
        self,
        window_manager: WindowManager,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._window_manager = window_manager
        self._sleeper = sleeper

    @property
    def target_exists(self) -> bool:
        return self._window_manager.target_exists

    @property
    def target_is_active(self) -> bool:
        return self._window_manager.target_is_active

    def restore(self) -> bool:
        return self._window_manager.restore()

    def activate(self) -> bool:
        return self._window_manager.activate()

    def show(self) -> bool:
        return self._window_manager.show()

    def click(self, relative_x: int, relative_y: int) -> None:
        self._window_manager.click(relative_x, relative_y)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> None:
        self._window_manager.drag(start_x, start_y, end_x, end_y, duration)

    def wait(self, seconds: float) -> None:
        self._sleeper(seconds)

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        return self._window_manager.screenshot(relative_region)

    def get_client_size(self) -> tuple[int, int]:
        return self._window_manager.get_client_size()


class InMemoryImageSource(ImageSource):
    """
    An ImageSource that serves crops from an in-memory image buffer.

    NOTE: This source returns views of the original buffer. Consumers MUST NOT
    modify the images returned by screenshot().
    """

    def __init__(self, full_image: MatLike):
        self._image = full_image
        self._height, self._width = full_image.shape[:2]

    @classmethod
    def cache_from(cls, other: ImageSource) -> "InMemoryImageSource":
        """
        Create an InMemoryImageSource by taking a full screenshot from another source.
        """
        return cls(other.screenshot())

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        if relative_region is None:
            return self._image

        # Slicing using p0 (top-left) and p1 (bottom-right)
        p0, p1 = relative_region.p0, relative_region.p1
        return self._image[p0.y : p1.y, p0.x : p1.x]

    def get_client_size(self) -> tuple[int, int]:
        return self._width, self._height
