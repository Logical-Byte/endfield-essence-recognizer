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
