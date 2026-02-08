from collections.abc import Sequence
from dataclasses import dataclass

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.core.recognition.brightness_detector import (
    BrightnessDetector,
    BrightnessDetectorProfile,
)
from endfield_essence_recognizer.deps import get_resolution_profile
from endfield_essence_recognizer.utils.image import to_gray_image
from endfield_essence_recognizer.utils.log import logger


@dataclass(frozen=True)
class AttributeLevelRecognizerProfile:
    """
    Configuration for AttributeLevelRecognizer.
    """

    brightness_profile: BrightnessDetectorProfile

    stats_level_icon_points: Sequence[Sequence[Point]]


def build_attribute_level_recognizer_profile() -> AttributeLevelRecognizerProfile:
    """
    Builds the AttributeLevelRecognizerProfile with hardcoded 1080p settings.
    """
    brightness_profile = BrightnessDetectorProfile(threshold=200, sample_radius=2)

    stats_level_icon_points = get_resolution_profile().STATS_LEVEL_ICON_POINTS

    return AttributeLevelRecognizerProfile(
        brightness_profile=brightness_profile,
        stats_level_icon_points=stats_level_icon_points,
    )


class AttributeLevelRecognizer:
    """
    Recognizes the level of an attribute based on the brightness of
    a series of icons.
    """

    def __init__(self, name: str, profile: AttributeLevelRecognizerProfile) -> None:
        self.name = name
        self.profile = profile
        self._brightness_detector = BrightnessDetector(
            f"{self.name}.BrightnessDetector", profile.brightness_profile
        )

        logger.debug(f"Created {self} with profile: {profile}")

    def __str__(self) -> str:
        return f"[{self.name}]"

    def recognize_level(self, image: MatLike, stat_index: int) -> int | None:
        """
        根据属性索引识别等级。

        Args:
            image: 全局图像（客户区截图）。
            stat_index: 属性索引 (0, 1, 2)。

        Returns:
            等级 (1-6) 或 None（识别失败）。
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
        if active_count > 0:
            return active_count
        return None
