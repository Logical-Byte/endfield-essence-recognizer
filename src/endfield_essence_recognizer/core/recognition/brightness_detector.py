"""
Detect the average brightness of a region in an image.
"""

from dataclasses import dataclass

import numpy as np
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.utils.image import (
    make_region_from_center,
    region_out_of_bounds,
)
from endfield_essence_recognizer.utils.log import logger


@dataclass(frozen=True)
class RegionBrightnessProfile:
    """实例化亮度检测所需的配置。"""

    threshold: int = 200
    """亮度阈值 (0-255)。当区域平均亮度超过此值时视为“激活”。"""
    sample_radius: int = 3
    """采样半径。以给定点为中心，采样 (2*radius+1)^2 个像素。"""


class BrightnessDetector:
    """
    一个简单的亮度检测器，用于判断图像中某个点周围的区域是否“足够亮”。
    """

    def __init__(self, profile: RegionBrightnessProfile) -> None:
        self.profile = profile

    def is_bright(self, image: MatLike, point: Point) -> bool:
        """
        检测指定坐标点周围区域是否激活（超过阈值）。

        Args:
            image: 灰度图像。
            point:待检测的中心点。

        Returns:
            True 表示亮色（激活），False 表示暗色（未激活）。
        """
        height, width = image.shape[:2]
        region = make_region_from_center(point, self.profile.sample_radius)
        if region_out_of_bounds(region, width, height):
            logger.warning(f"坐标点 {point} 超出图像范围")
            return False

        roi_image = image[region.y0 : region.y1, region.x0 : region.x1]
        avg_brightness = float(np.mean(roi_image))  # type: ignore

        is_active = avg_brightness > self.profile.threshold
        logger.trace(
            f"坐标点 {point} 亮度={avg_brightness:.1f}, 状态={'亮色' if is_active else '暗色'}"
        )
        return is_active
