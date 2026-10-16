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
    """亮点判定参数：阈值与采样半径。"""

    search_dx: int
    """亮点位置的水平搜索半径（逻辑像素）。"""

    search_dy: int
    """亮点位置的垂直搜索半径（逻辑像素）。"""

    relative_threshold: float
    """亮点判定阈值还要求不低于“本行最亮采样值”的该比例。"""


def build_attribute_level_recognizer_profile() -> AttributeLevelRecognizerProfile:
    """
    Builds the AttributeLevelRecognizerProfile (brightness only; icon points come from ResolutionProfile).
    """
    # 等级亮点是纯白高光（中心亮度 254），而面板背景、词条文字、稀有度色条都
    # 远低于该阈值。
    brightness_profile = BrightnessDetectorProfile(threshold=200, sample_radius=2)
    return AttributeLevelRecognizerProfile(
        brightness_profile=brightness_profile,
        # 相邻亮点间距 17px、相邻词条行间距 28px：搜索半径必须小于间距的一半
        # （8.5px），否则某个暗点的搜索窗口会覆盖到相邻亮点上，把等级多计一级。
        # 两版实测漂移不超过 2.5px，5px 足够覆盖且留有余量。
        search_dx=5,
        search_dy=5,
        # 选中行下方的底色带（实测最亮约 135）是面板上最亮的“非亮点”元素：绝对
        # 阈值 200 能挡住它，但为防 UI 以后把它调得更亮，再要求达到本行最亮采样值
        # 的 60%（亮点间亮度一致，实测 247~254），把阈值抬到亮点与底色带之间。
        relative_threshold=0.6,
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

    def recognize_level(
        self,
        image: MatLike,
        stat_index: int,
        resolution_profile: ResolutionProfile,
    ) -> int | None:
        """
        根据属性索引识别等级。

        `resolution_profile` 给出的只是标称坐标：游戏 UI 改版会让亮点相对标称位置
        整体漂移（图标加大、行高变化），因此在标称点附近的搜索窗口内定位真正的亮点
        再判断亮暗，窗口大小由 profile 的 `search_dx` / `search_dy` 决定。

        亮点是纯白高光，暗点处的采样亮度与背景相当，两者相差悬殊，所以按“亮点连续
        点亮”的规则累计等级 —— 遇到第一个暗点就停止计数，与游戏内等级高光的渲染
        方式一致。

        Args:
            image: 全局图像（客户区截图）。
            stat_index: 属性索引 (0, 1, 2)。
            resolution_profile: 当前分辨率的布局配置，提供等级图标标称坐标。

        Returns:
            等级 (1-6) 或 None（识别失败）。
        """
        gray = to_gray_image(image)
        icon_points = resolution_profile.STATS_LEVEL_ICON_POINTS[stat_index]
        # 每个亮点都要试遍搜索窗口，逐点计算区域均值太慢，先整张算好再查表
        brightness_map = self._brightness_detector.build_brightness_map(gray)

        found = [
            self._brightness_detector.locate_dot(
                brightness_map,
                nominal_point,
                self.profile.search_dx,
                self.profile.search_dy,
            )
            for nominal_point in icon_points
        ]
        # 同一行亮点的亮度由同一套 UI 渲染，用本行最亮采样值把阈值抬到亮点与背景
        # 之间，避免把行内的亮色 UI（如选中底色带）当成亮点
        threshold = max(
            self.profile.brightness_profile.threshold,
            max(brightness for _, brightness in found)
            * self.profile.relative_threshold,
        )

        active_count = 0
        for nominal_point, (found_point, brightness) in zip(
            icon_points, found, strict=True
        ):
            is_active = brightness > threshold
            logger.trace(
                f"{self}属性 {stat_index} 标称点 {nominal_point} → "
                f"采样点 {found_point} 亮度={brightness:.1f} 阈值={threshold:.1f}, "
                f"状态={'亮色' if is_active else '暗色'}"
            )
            if is_active:
                active_count += 1
            else:
                # 假设白色图标是连续的，遇到暗色后停止计数
                break

        # 根据激活图标数量返回等级
        if active_count > 0:
            return active_count
        return None
