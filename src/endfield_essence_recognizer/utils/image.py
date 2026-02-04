"""
Utils for image processing.
"""

from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point, Region

type Slice = slice | tuple[slice, slice]


def load_image(
    image_like: str | Path | bytes | MatLike,
    flags: int = cv2.IMREAD_COLOR,
) -> MatLike:
    if isinstance(image_like, str | Path):
        image = cv2.imdecode(np.fromfile(image_like, dtype=np.uint8), flags)
    elif isinstance(image_like, bytes | bytearray | memoryview):
        image = cv2.imdecode(np.frombuffer(image_like, dtype=np.uint8), flags)
    else:
        image = image_like

    if image is None:
        raise ValueError("Failed to load image from the provided input.")

    return image


def to_gray_image(image: MatLike) -> MatLike:
    """将图像转换为灰度图像。"""
    if len(image.shape) == 2:
        return image  # 已经是灰度图
    elif len(image.shape) == 3:
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    raise ValueError("Unsupported image format for grayscale conversion.")


def save_image(
    image: MatLike,
    path: str | Path,
    ext: str = ".png",
    params: Sequence[int] | None = None,
) -> bool:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success, buffer = cv2.imencode(ext, image, params or [])
    path.write_bytes(buffer)
    return success


def linear_operation(image: MatLike, min_value: int, max_value: int) -> MatLike:
    image = (image.astype(np.float64) - min_value) / (max_value - min_value) * 255
    return np.clip(image, 0, 255).astype(np.uint8)


def scope_to_slice(scope: Region | None) -> Slice:
    """ROI -> (slice(y0, y1), slice(x0, x1))"""
    if scope is None:
        return slice(None), slice(None)
    return slice(scope.y0, scope.y1), slice(scope.x0, scope.x1)


def make_region_from_center(center: Point, radius: int) -> Region:
    """
    从中心点和半径创建一个正方形区域。区域边长为 2*radius + 1。

    e.g. , center=(10,10), radius=2 -> Region((8,8),(13,13))
    """
    return Region(
        Point(center.x - radius, center.y - radius),
        Point(center.x + radius + 1, center.y + radius + 1),
    )


def region_out_of_bounds(
    region: Region,
    image_width: int,
    image_height: int,
) -> bool:
    """检查区域是否超出图像范围。"""
    return not (
        0 <= region.x0 < region.x1 <= image_width
        and 0 <= region.y0 < region.y1 <= image_height
    )
