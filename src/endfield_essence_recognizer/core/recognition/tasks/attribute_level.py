from collections.abc import Sequence
from dataclasses import dataclass

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.core.recognition.brightness_detector import (
    BrightnessDetector,
    RegionBrightnessProfile,
)
from endfield_essence_recognizer.utils.image import to_gray_image

# Hardcoded 1080p coordinates for attribute level icons
_STATS_LEVEL_ICONS: list[Sequence[Point]] = [
    [
        Point(1503, 395),  # +1
        Point(1520, 395),  # +2
        Point(1538, 395),  # +3
        Point(1554, 395),  # +4
    ],
    [
        Point(1503, 452),  # +1
        Point(1520, 452),  # +2
        Point(1538, 452),  # +3
        Point(1554, 452),  # +4
    ],
    [
        Point(1503, 507),  # +1
        Point(1520, 507),  # +2
        Point(1538, 507),  # +3
        Point(1554, 507),  # +4
    ],
]


@dataclass(frozen=True)
class AttributeLevelRecognizerProfile:
    """
    Configureation for AttributeLevelRecognizer.
    """

    brightness_profile: RegionBrightnessProfile

    stats_level_icon_points: list[Sequence[Point]]


def build_attribute_level_recognizer_profile() -> AttributeLevelRecognizerProfile:
    """
    Builds the AttributeLevelRecognizerProfile with hardcoded 1080p settings.
    """
    # config the brightness detector profile
    brightness_profile = RegionBrightnessProfile(threshold=200, sample_radius=2)

    # hardcode the 1080p icon points
    stats_level_icon_points = _STATS_LEVEL_ICONS

    return AttributeLevelRecognizerProfile(
        brightness_profile=brightness_profile,
        stats_level_icon_points=stats_level_icon_points,
    )


class AttributeLevelRecognizer:
    """
    Recognizes the level of an attribute based on the brightness of
    a series of icons.
    """

    def __init__(self, profile: AttributeLevelRecognizerProfile) -> None:
        self.profile = profile
        self._brightness_detector = BrightnessDetector(profile.brightness_profile)

    def recognize_level(self, image: MatLike, stat_index: int) -> int | None:
        """
        根据属性索引识别等级。

        Args:
            image: 全局图像（客户区截图）。
            stat_index: 属性索引 (0, 1, 2)。

        Returns:
            等级 (1-4) 或 None（识别失败）。
        """
        gray = to_gray_image(image)
        icon_points = self.profile.stats_level_icon_points[stat_index]

        # 检测每个图标的状态
        active_count = 0
        for p in icon_points:
            is_active = self._brightness_detector.is_bright(gray, p)
            if is_active:
                active_count += 1
            else:
                # 假设白色图标是连续的，遇到暗色后停止计数
                break

        # 根据激活图标数量返回等级
        if 1 <= active_count <= 4:
            return active_count
        return None
