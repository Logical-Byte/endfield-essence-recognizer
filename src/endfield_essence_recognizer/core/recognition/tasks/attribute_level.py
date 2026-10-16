from dataclasses import dataclass

from cv2.typing import MatLike

from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.recognition.brightness_detector import (
    BrightnessDetector,
    BrightnessDetectorProfile,
)
from endfield_essence_recognizer.utils.image import (
    scope_to_slice,
    to_gray_image,
)
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
    # 等级亮点是纯白高光（实测中心亮度 252~253），而面板内亮点之外最亮的像素也只有
    # 195，两者相差 57 以上，绝对阈值取两者之间即可。
    brightness_profile = BrightnessDetectorProfile(threshold=200, sample_radius=2)
    return AttributeLevelRecognizerProfile(
        brightness_profile=brightness_profile,
        # 相邻亮点间距 17px、相邻词条行间距 56px：搜索半径必须分别小于两者的一半
        # （8.5px / 28px），否则某个暗点的搜索窗口会覆盖到相邻亮点上，把等级多计
        # 一级。两版实测漂移不超过 2.5px，5px 足够覆盖且留有余量。
        search_dx=5,
        search_dy=5,
        # 8bit 灰度图的采样值上界是 255，所以相对阈值能被 max() 采纳的条件是
        # row_max * relative_threshold > 200。实测 row_max ≈ 253，因此该值必须
        # 大于 200 / 253 ≈ 0.79 才会生效；取 0.8 时阈值约为 202，正好把面板内
        # 最亮 195 的干扰像素挡在门外，同时远低于亮点本身的 252。
        relative_threshold=0.8,
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

    def _level_brightness_map(
        self,
        image: MatLike,
        resolution_profile: ResolutionProfile,
    ) -> tuple[MatLike, Point] | None:
        """
        只为等级亮点所在的一小块区域预计算亮度图。

        等级亮点只集中在面板右侧一条窄带上（1080p 下约 100x127 像素，占整帧
        0.6%），因此先把这一块裁出来再去灰度、滤波；对整帧做同样的事开销要大两个
        数量级，而 `recognize_levels` 每识别一个基质就要用一次。

        Args:
            image: 全局图像（客户区截图）。
            resolution_profile: 当前分辨率的布局配置，提供等级图标标称坐标。

        Returns:
            (亮度图, 该亮度图左上角在 `image` 中的坐标)；图像尺寸不足以覆盖这一块
            时返回 None。
        """
        all_points = [
            point
            for icon_points in resolution_profile.STATS_LEVEL_ICON_POINTS
            for point in icon_points
        ]
        # 标称坐标附近的搜索窗口（±search_d*）与采样窗口（±sample_radius）都可能
        # 取到图像内容，裁剪范围必须把它们全部包含进来
        margin = (
            max(self.profile.search_dx, self.profile.search_dy)
            + self.profile.brightness_profile.sample_radius
        )
        region = Region(
            Point(
                min(point.x for point in all_points) - margin,
                min(point.y for point in all_points) - margin,
            ),
            Point(
                max(point.x for point in all_points) + margin + 1,
                max(point.y for point in all_points) + margin + 1,
            ),
        )
        # 窗口尺寸小于布局标称分辨率时裁剪会越出画面，必须夹回图像范围，否则空数组
        # 会在 cvtColor 上抛异常；夹完仍无交集就说明亮点根本不在画面内
        height, width = image.shape[:2]
        left, top = max(region.x0, 0), max(region.y0, 0)
        right, bottom = min(region.x1, width), min(region.y1, height)
        if left >= right or top >= bottom:
            logger.debug(
                f"{self} 图像尺寸 {width}x{height} 未覆盖等级亮点区域 "
                f"({region.x0},{region.y0})-({region.x1},{region.y1})，按识别失败处理"
            )
            return None
        clipped = Region(Point(left, top), Point(right, bottom))
        # 先裁剪再转灰度：转灰度的开销与像素数成正比，先转整帧是本块裁剪的 150 倍
        roi = to_gray_image(image[scope_to_slice(clipped)])
        return self._brightness_detector.build_brightness_map(roi), clipped.p0

    def recognize_levels(
        self,
        image: MatLike,
        resolution_profile: ResolutionProfile,
    ) -> list[int | None]:
        """
        依次识别三行词条的等级，三行共用同一份亮度图。

        等级亮点只占整帧的一小块，但 `recognize_level` 单独调用时无法把这笔开销摊
        到三行上，所以批量识别走这个入口。

        Args:
            image: 全局图像（客户区截图）。
            resolution_profile: 当前分辨率的布局配置。

        Returns:
            三个等级 (1-6) 或 None 的列表，按属性索引排列；图像尺寸不足以覆盖等级
            亮点区域时三个都是 None。
        """
        built = self._level_brightness_map(image, resolution_profile)
        if built is None:
            return [None] * len(resolution_profile.STATS_LEVEL_ICON_POINTS)
        brightness_map, map_origin = built
        return [
            self._recognize_level_from_map(
                stat_index, resolution_profile, brightness_map, map_origin
            )
            for stat_index in range(len(resolution_profile.STATS_LEVEL_ICON_POINTS))
        ]

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
        built = self._level_brightness_map(image, resolution_profile)
        if built is None:
            return None
        brightness_map, map_origin = built
        return self._recognize_level_from_map(
            stat_index, resolution_profile, brightness_map, map_origin
        )

    def _recognize_level_from_map(
        self,
        stat_index: int,
        resolution_profile: ResolutionProfile,
        brightness_map: MatLike,
        map_origin: Point,
    ) -> int | None:
        """
        在已算好的亮度图上识别一行词条的等级。

        Args:
            stat_index: 属性索引 (0, 1, 2)。
            resolution_profile: 当前分辨率的布局配置，提供等级图标标称坐标。
            brightness_map: `_level_brightness_map` 得到的亮度图。
            map_origin: `brightness_map` 左上角在整帧中的坐标。

        Returns:
            等级 (1-6) 或 None（识别失败）。
        """
        icon_points = [
            # 亮度图只是整帧的一小块，标称坐标要换算成图内坐标
            Point(point.x - map_origin.x, point.y - map_origin.y)
            for point in resolution_profile.STATS_LEVEL_ICON_POINTS[stat_index]
        ]
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
        row_max = max(brightness for _, brightness in found)
        threshold = max(
            self.profile.brightness_profile.threshold,
            row_max * self.profile.relative_threshold,
        )

        active_count = 0
        for nominal_point, (found_point, brightness) in zip(
            icon_points, found, strict=True
        ):
            is_active = brightness > threshold
            logger.trace(
                f"{self}属性 {stat_index} 标称点 "
                f"({nominal_point.x + map_origin.x}, {nominal_point.y + map_origin.y}) → "
                f"采样点 ({found_point.x + map_origin.x}, {found_point.y + map_origin.y}) "
                f"亮度={brightness:.1f} 阈值={threshold:.1f} "
                f"(本行最亮 {row_max:.1f}), 状态={'亮色' if is_active else '暗色'}"
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
