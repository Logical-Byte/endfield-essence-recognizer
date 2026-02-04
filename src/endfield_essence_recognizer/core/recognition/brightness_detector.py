"""
Detect the average brightness of a region in an image.
"""

from collections.abc import Sequence

import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.utils.image import to_gray_image
from endfield_essence_recognizer.utils.log import logger

# original helper functions for brightness detection


def detect_icon_state_at_point(image: MatLike, x: int, y: int, radius: int = 3) -> bool:
    """
    检测指定坐标点的图标状态。

    Args:
        image: 全局灰度图像（客户区截图）
        x: 图标中心 x 坐标（客户区像素坐标）
        y: 图标中心 y 坐标（客户区像素坐标）
        radius: 采样半径

    Returns:
        True 表示白色/亮色（激活），False 表示黑色/暗色（未激活）
    """
    height, width = image.shape[:2]
    if x < radius or x >= width - radius or y < radius or y >= height - radius:
        logger.warning(f"坐标点 ({x}, {y}) 超出图像范围")
        return False

    # 提取坐标点周围区域的平均亮度
    region = image[y - radius : y + radius + 1, x - radius : x + radius + 1]
    avg_brightness = np.mean(region)  # type: ignore

    # 阈值：大于 200 认为是白色/亮色（激活）
    is_active = avg_brightness > 200
    logger.trace(
        f"坐标点 ({x}, {y}) 亮度={avg_brightness:.1f}, 状态={'白色' if is_active else '灰色'}"
    )
    return is_active


def recognize_level_from_icon_points(
    image: MatLike,
    icon_points: Sequence[Point],
    radius: int = 2,
) -> int | None:
    """
    根据坐标点列表识别等级。

    Args:
        image: 全局图像（客户区截图）
        icon_points: 4个图标的坐标点列表 [Point(x1,y1), Point(x2,y2), Point(x3,y3), Point(x4,y4)]
        radius: 采样半径

    Returns:
        等级 (1-4) 或 None（识别失败）
    """
    gray = to_gray_image(image)

    # 检测每个图标的状态
    active_count = 0
    for i, p in enumerate(icon_points):
        is_active = detect_icon_state_at_point(gray, p.x, p.y, radius)
        logger.trace(
            f"图标 {i + 1} ({p.x},{p.y}) 状态: {'白色' if is_active else '灰色'}"
        )
        if is_active:
            active_count += 1
        else:
            # 假设白色图标是连续的，遇到黑色后不再计数
            break

    # 根据激活图标数量返回等级
    if 1 <= active_count <= 4:
        return active_count
    else:
        return None
