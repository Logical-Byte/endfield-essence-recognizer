from collections.abc import Sequence

import numpy as np

from .base import Point, Region, ResolutionProfile


class Resolution1080p(ResolutionProfile):
    @property
    def RESOLUTION(self) -> tuple[int, int]:
        return (1920, 1080)

    @property
    def essence_icon_x_list(self) -> Sequence[int]:
        return np.linspace(128, 1374, 9).astype(int).tolist()

    @property
    def essence_icon_y_list(self) -> Sequence[int]:
        return np.linspace(196, 819, 5).astype(int).tolist()

    @property
    def ESSENCE_UI_ROI(self) -> Region:
        return Region(Point(38, 66), Point(143, 106))

    @property
    def AREA(self) -> Region:
        return Region(Point(1465, 79), Point(1883, 532))

    @property
    def DEPRECATE_BUTTON_POS(self) -> Point:
        return Point(1807, 284)

    @property
    def LOCK_BUTTON_POS(self) -> Point:
        return Point(1839, 286)

    @property
    def DEPRECATE_BUTTON_ROI(self) -> Region:
        return Region(Point(1790, 270), Point(1823, 302))

    @property
    def LOCK_BUTTON_ROI(self) -> Region:
        return Region(Point(1825, 270), Point(1857, 302))

    @property
    def STATS_0_ROI(self) -> Region:
        return Region(Point(1508, 358), Point(1700, 390))

    @property
    def STATS_1_ROI(self) -> Region:
        return Region(Point(1508, 416), Point(1700, 448))

    @property
    def STATS_2_ROI(self) -> Region:
        return Region(Point(1508, 468), Point(1700, 500))

    @property
    def MASK_ESSENCE_REGION_UID(self) -> Region:
        return Region(Point(0, 1040), Point(270, 1080))

    @property
    def MASK_ESSENCE_REGION_CURRENCY(self) -> Region:
        return Region(Point(1340, 20), Point(1810, 70))

    @property
    def STATS_LEVEL_ICON_POINTS(self) -> list[list[Point]]:
        xs = np.linspace(1503, 1588, 6)
        ys = np.linspace(395, 507, 3)
        return [[Point(round(x), round(y)) for x in xs] for y in ys]

    @property
    def LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI(self) -> Region:
        return Region(Point(340, 68), Point(702, 208))

    @property
    def DELIVERY_JOB_REWARD_ROI(self) -> Region:
        return Region(Point(1251, 252), Point(1413, 989))

    @property
    def DELIVERY_JOB_REFRESH_BUTTON_POINT(self) -> Point:
        return Point(1745, 1003)

    @property
    def DRAG_START_POS(self) -> Point:
        # 拖动起始位置：基质图标区域底部
        return Point(750, 870)

    @property
    def DRAG_END_POS(self) -> Point:
        # 拖动结束位置：向上滑动750像素
        return Point(750, 50)

    @property
    def DRAG_DURATION(self) -> float:
        # 拖动持续时间 1.0 秒，减缓速度让游戏UI能跟上
        return 1.0

    @property
    def SCROLLBAR_CHECK_POS(self) -> Point:
        # 滚动条检测位置 (1453, 950) 附近
        return Point(1453, 950)

    @property
    def SCROLLBAR_COLOR(self) -> tuple[int, int, int]:
        # 滚动条颜色 #C7C5C5 的 BGR 格式
        return (197, 197, 199)

    @property
    def SCROLLBAR_BG_COLOR(self) -> tuple[int, int, int]:
        # 滚动条背景色 #2B2927 的 BGR 格式
        return (39, 41, 43)

    @property
    def SCROLLBAR_COLOR_TOLERANCE(self) -> int:
        # 颜色容差值，增大以适应不同分辨率下的颜色偏差
        return 90
