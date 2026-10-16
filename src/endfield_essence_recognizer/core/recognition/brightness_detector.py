"""
Detect the average brightness of a region in an image.
"""

from dataclasses import dataclass

import cv2
from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.utils.image import (
    make_region_from_center,
    region_out_of_bounds,
)
from endfield_essence_recognizer.utils.log import logger


@dataclass(frozen=True)
class BrightnessDetectorProfile:
    """实例化亮度检测所需的配置。"""

    threshold: int = 200
    """亮度阈值 (0-255)。当区域平均亮度超过此值时视为“激活”。"""
    sample_radius: int = 3
    """采样半径。采样区域为以给定点为中心，边长为 `(2 * sample_radius + 1)` 的正方形区域。"""


class BrightnessDetector:
    """
    一个简单的亮度检测器，用于判断图像中某个点周围的区域是否“足够亮”。
    """

    def __init__(self, name: str, profile: BrightnessDetectorProfile) -> None:
        self.name = name
        self.profile = profile

    def __str__(self) -> str:
        return f"[{self.name}]"

    def build_brightness_map(self, image: MatLike) -> MatLike:
        """
        预计算整张图的采样亮度，之后每次采样都退化成一次数组取值。

        识别等级需要在同一张截图上反复采样（每个亮点、每个候选偏移各一次），
        逐点计算区域均值会成为瓶颈；这里用一次盒式滤波把“以该像素为中心采样”
        的结果整张算好。

        Args:
            image: 灰度图像。

        Returns:
            与输入同尺寸的 float32 亮度图。
        """
        kernel_size = 2 * self.profile.sample_radius + 1
        return cv2.boxFilter(
            image,
            ddepth=cv2.CV_32F,
            ksize=(kernel_size, kernel_size),
            normalize=True,
            borderType=cv2.BORDER_REPLICATE,
        )

    def locate_dot(
        self,
        brightness_map: MatLike,
        point: Point,
        search_dx: int = 0,
        search_dy: int = 0,
    ) -> tuple[Point, float]:
        """
        在以 `point` 为中心的窗口内寻找最亮的采样中心。

        游戏 UI 改版会让标称坐标相对实际亮点产生整体偏移，因此在
        `search_dx` × `search_dy` 的窗口内滑动采样框，取亮度最高的位置。
        两个搜索半径都为 0 时直接返回 `point` 本身的采样结果。

        Args:
            brightness_map: `build_brightness_map` 的输出。
            point: 标称的检测中心点。
            search_dx: 水平搜索半径（逻辑像素）。
            search_dy: 垂直搜索半径（逻辑像素）。

        Returns:
            (最亮采样中心, 该中心的平均亮度)。窗口完全越界时返回 (point, 0.0)。
        """
        height, width = brightness_map.shape[:2]
        sample_radius = self.profile.sample_radius

        best_point = point
        best_brightness: float | None = None
        for offset_y in range(-search_dy, search_dy + 1):
            y = point.y + offset_y
            for offset_x in range(-search_dx, search_dx + 1):
                x = point.x + offset_x
                region = make_region_from_center(Point(x, y), sample_radius)
                if region_out_of_bounds(region, width, height):
                    # 搜索窗口可能越出图像边缘，跳过该候选中心
                    continue
                brightness = float(brightness_map[y, x])
                if best_brightness is None or brightness > best_brightness:
                    best_point = Point(x, y)
                    best_brightness = brightness

        if best_brightness is None:
            logger.warning(f"{self}坐标点 {point} 的搜索窗口完全超出图像范围")
            return point, 0.0

        return best_point, best_brightness
