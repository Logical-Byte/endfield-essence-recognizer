from dataclasses import dataclass

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.recognition.brightness_detector import (
    BrightnessDetector,
    BrightnessDetectorProfile,
)
from endfield_essence_recognizer.utils.image import to_gray_image
from endfield_essence_recognizer.utils.log import logger


@dataclass(frozen=True)
class AttributeLevelRecognizerProfile:
    """
    Configuration for AttributeLevelRecognizer.
    """

    brightness_profile: BrightnessDetectorProfile


def build_attribute_level_recognizer_profile() -> AttributeLevelRecognizerProfile:
    """
    Builds the AttributeLevelRecognizerProfile (brightness only; icon points come from ResolutionProfile).
    """
    brightness_profile = BrightnessDetectorProfile(threshold=200, sample_radius=2)
    return AttributeLevelRecognizerProfile(brightness_profile=brightness_profile)


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

    def recognize_level(
        self,
        image: MatLike,
        stat_index: int,
        resolution_profile: ResolutionProfile,
    ) -> int | None:
        """
        根据属性索引识别等级。

        Args:
            image: 全局图像（客户区截图）。
            stat_index: 属性索引 (0, 1, 2)。
            resolution_profile: 当前分辨率的布局配置，提供等级图标坐标。

        Returns:
            等级 (1-4) 或 None（识别失败）。
        """
        gray = to_gray_image(image)
        icon_points = resolution_profile.stats_level_icon_points[stat_index]

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
