from collections.abc import Sequence
from typing import NamedTuple, Protocol


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
    def MASK_ESSENCE_REGION_UID(self) -> Region:
        """在基质界面截图中需要遮罩的 UID 区域。"""
        ...

    @property
    def MASK_ESSENCE_REGION_CURRENCY(self) -> Region:
        """在基质界面截图中需要遮罩的货币区区域。"""
        ...

    @property
    def STATS_LEVEL_ICON_POINTS(self) -> list[list[Point]]:
        """属性等级图标的坐标列表，按照属性索引和等级顺序排列。"""
        ...

    @property
    def LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI(self) -> Region:
        """用于判定是否在派遣任务列表场景的 ROI 区域。"""
        ...

    @property
    def DELIVERY_JOB_REWARD_ROI(self) -> Region:
        """派遣任务奖励扫描区域。"""
        ...

    @property
    def DELIVERY_JOB_REFRESH_BUTTON_POINT(self) -> Point:
        """运送委托列表刷新按钮坐标。"""
        ...

    @property
    def DRAG_START_POS(self) -> Point:
        """
        拖动翻页的起始位置。

        在基质图标区域中，用于开始向上拖动的位置。
        """
        ...

    @property
    def DRAG_END_POS(self) -> Point:
        """
        拖动翻页的结束位置。

        在基质图标区域中，用于结束向上拖动的位置（向上拖动）。
        """
        ...

    @property
    def DRAG_DURATION(self) -> float:
        """
        拖动操作的持续时间（秒）。
        """
        ...

    @property
    def SCROLLBAR_CHECK_POS(self) -> Point:
        """
        滚动条检测位置。

        用于检测是否滚动到底部的像素坐标。
        如果该位置有滚动条颜色 (#C7C5C5)，则表示已到达底部。
        """
        ...

    @property
    def SCROLLBAR_COLOR(self) -> tuple[int, int, int]:
        """
        滚动条的颜色 (BGR 格式)。

        默认值为 #C7C5C5 的 BGR 格式 (197, 197, 199)。
        """
        ...

    @property
    def SCROLLBAR_BG_COLOR(self) -> tuple[int, int, int]:
        """
        滚动条背景/底色 (BGR 格式)。

        默认值为 #2B2927 的 BGR 格式 (39, 41, 43)。
        """
        ...

    @property
    def SCROLLBAR_COLOR_TOLERANCE(self) -> int:
        """
        滚动条颜色匹配的容差值。

        用于判断检测位置的颜色是否接近滚动条颜色。
        """
        ...
