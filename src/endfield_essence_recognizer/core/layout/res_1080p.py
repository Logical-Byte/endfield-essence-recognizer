from typing import Sequence

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
    def STATS_0_LEVEL_ICONS(self) -> Sequence[Point]:
        return [
            Point(1503, 395),  # +1
            Point(1520, 395),  # +2
            Point(1538, 395),  # +3
            Point(1554, 395),  # +4
        ]

    @property
    def STATS_1_LEVEL_ICONS(self) -> Sequence[Point]:
        return [
            Point(1503, 452),  # +1
            Point(1520, 452),  # +2
            Point(1538, 452),  # +3
            Point(1554, 452),  # +4
        ]

    @property
    def STATS_2_LEVEL_ICONS(self) -> Sequence[Point]:
        return [
            Point(1503, 507),  # +1
            Point(1520, 507),  # +2
            Point(1538, 507),  # +3
            Point(1554, 507),  # +4
        ]

    @property
    def LEVEL_ICON_SAMPLE_RADIUS(self) -> int:
        return 2
