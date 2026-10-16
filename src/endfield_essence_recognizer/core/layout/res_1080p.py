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
        """第一个属性词条的识别区域。

        词条文字实测：旧版 y 363~383、新版 y 367~386（两版合起来 363~386，高 24px）。
        区域取 357~401，即文字上方 6px、下方 15px —— 相对扫描到的两版文字并集整体
        偏下 2.5px，不是对称居中：上边界只比原来的 32px 区域上移 1px，下边界下移
        11px。余量不对称没有影响，因为模板匹配只要求文字完整落在区域内 —— 只要
        文字不被区域边界切掉，整体偏移几个像素不改变匹配，余量决定的是还能容忍 UI
        再漂移多少，而窗口内的 ±4px 漂移在测试里覆盖过。原来 32px 高的区域只留
        4~8px，再漂移 3px 文字边缘就会被切掉、匹配分数从 0.9 掉到 0.5 以下。
        """
        return Region(Point(1508, 357), Point(1700, 401))

    @property
    def STATS_1_ROI(self) -> Region:
        """第二个属性词条的识别区域，余量说明见 `STATS_0_ROI`。"""
        return Region(Point(1508, 413), Point(1700, 457))

    @property
    def STATS_2_ROI(self) -> Region:
        """第三个属性词条的识别区域，余量说明见 `STATS_0_ROI`。"""
        return Region(Point(1508, 469), Point(1700, 513))

    @property
    def RARITY_ROI(self) -> Region:
        return Region(Point(1468, 78), Point(1472, 82))

    @property
    def MASK_ESSENCE_REGION_UID(self) -> Region:
        return Region(Point(0, 1040), Point(270, 1080))

    @property
    def MASK_ESSENCE_REGION_CURRENCY(self) -> Region:
        return Region(Point(1340, 20), Point(1810, 70))

    @property
    def STATS_LEVEL_ICON_POINTS(self) -> list[list[Point]]:
        """三行词条等级亮点的标称坐标。

        Y 取旧版（实测中心 y=397/453/509）与新版（实测中心 y=400/456/512）的
        中点：`AttributeLevelRecognizer` 以这些坐标为基准在附近搜索真正的亮点，
        取中点可让两版 UI 各自都留出对称的漂移余量。
        """
        xs = np.linspace(1503, 1588, 6)
        ys = (399, 455, 511)
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
        """拖动起始位置：基质图标区域底部"""
        return Point(750, 870)

    @property
    def DRAG_END_POS(self) -> Point:
        """拖动结束位置：向上滑动到顶部"""
        return Point(750, 50)

    @property
    def SCROLLBAR_CHECK_POS(self) -> Point:
        """滚动条检测位置，用于判断是否到达底部"""
        return Point(1453, 950)

    @property
    def SCROLLBAR_TOP_CHECK_POS(self) -> Point:
        """滚动条顶部检测位置，用于判断是否回到第一页"""
        return Point(1453, 130)
