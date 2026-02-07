import time
from typing import Callable

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

    def wait(self, seconds: float) -> None:
        self._sleeper(seconds)

    def screenshot(self, relative_region: Region | None = None) -> MatLike:
        return self._window_manager.screenshot(relative_region)

    def get_client_size(self) -> tuple[int, int]:
        return self._window_manager.get_client_size()
