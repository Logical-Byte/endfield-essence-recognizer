from typing import Protocol, runtime_checkable

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Region


@runtime_checkable
class ImageSource(Protocol):
    def screenshot(self, relative_region: Region | None = None) -> MatLike: ...

    def get_client_size(self) -> tuple[int, int]: ...


@runtime_checkable
class WindowActions(Protocol):
    @property
    def target_exists(self) -> bool: ...

    @property
    def target_is_active(self) -> bool: ...

    def restore(self) -> bool: ...

    def activate(self) -> bool: ...

    def click(self, relative_x: int, relative_y: int) -> None: ...
