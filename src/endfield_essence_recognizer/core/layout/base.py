from typing import NamedTuple, Protocol, Sequence


class Point(NamedTuple):
    x: int
    y: int


class Region(NamedTuple):
    p0: Point
    p1: Point

    @property
    def x0(self) -> int:
        return self.p0.x

    @property
    def y0(self) -> int:
        return self.p0.y

    @property
    def x1(self) -> int:
        return self.p1.x

    @property
    def y1(self) -> int:
        return self.p1.y


class ResolutionProfile(Protocol):
    """
    游戏客户区分辨率相关的布局配置。

    为 `EssenceScanner` 提供所有必要的 ROI 、点击坐标等布局信息。也可包含其他与分辨率相关的配置。
    """

    @property
    def RESOLUTION(self) -> tuple[int, int]:
        """预期的游戏客户区分辨率 (宽, 高)。"""
        ...

    @property
    def essence_icon_x_list(self) -> Sequence[int]:
        """
        基质图标网格的 X 坐标列表。

        在水平轴上，基质图标的坐标列表。游戏中基质图标排列为 9 列，因此应包含 9 个元素。
        """
        ...

    @property
    def essence_icon_y_list(self) -> Sequence[int]:
        """
        基质图标网格的 Y 坐标列表。

        在垂直轴上，基质图标的坐标列表。游戏中基质图标排列为 5 行，因此应包含 5 个元素。
        """
        ...

    @property
    def ESSENCE_UI_ROI(self) -> Region:
        """用于判定是否在基质界面的 ROI 区域。"""
        ...

    @property
    def AREA(self) -> Region:
        """基质信息面板的整体区域。"""
        ...

    @property
    def DEPRECATE_BUTTON_POS(self) -> Point:
        """弃用按钮的点击坐标。"""
        ...

    @property
    def LOCK_BUTTON_POS(self) -> Point:
        """锁定按钮的点击坐标。"""
        ...

    @property
    def DEPRECATE_BUTTON_ROI(self) -> Region:
        """弃用按钮的状态识别区域。"""
        ...

    @property
    def LOCK_BUTTON_ROI(self) -> Region:
        """锁定按钮的状态识别区域。"""
        ...

    @property
    def STATS_0_ROI(self) -> Region:
        """第一个属性词条的识别区域。"""
        ...

    @property
    def STATS_1_ROI(self) -> Region:
        """第二个属性词条的识别区域。"""
        ...

    @property
    def STATS_2_ROI(self) -> Region:
        """第三个属性词条的识别区域。"""
        ...

    @property
    def STATS_0_LEVEL_ICONS(self) -> Sequence[Point]:
        """第一个属性各等级 (+1 到 +4) 图标的采样坐标点。"""
        ...

    @property
    def STATS_1_LEVEL_ICONS(self) -> Sequence[Point]:
        """第二个属性各等级 (+1 到 +4) 图标的采样坐标点。"""
        ...

    @property
    def STATS_2_LEVEL_ICONS(self) -> Sequence[Point]:
        """第三个属性各等级 (+1 到 +4) 图标的采样坐标点。"""
        ...

    @property
    def LEVEL_ICON_SAMPLE_RADIUS(self) -> int:
        """等级图标状态采样的半径。"""
        ...
