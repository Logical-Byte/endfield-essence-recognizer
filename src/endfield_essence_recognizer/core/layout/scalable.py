"""
基于基准 1080p 布局按比例缩放到任意分辨率的配置。

基准坐标，通过 (target_w / 1920, target_h / 1080) 缩放计算得到
"""

from collections.abc import Sequence

from .base import Point, Region, ResolutionProfile
from .res_1080p import Resolution1080p

_REF_W = 1920
_REF_H = 1080


def _scale_point(p: Point, sx: float, sy: float) -> Point:
    return Point(round(p.x * sx), round(p.y * sy))


def _scale_region(r: Region, sx: float, sy: float) -> Region:
    return Region(_scale_point(r.p0, sx, sy), _scale_point(r.p1, sx, sy))


class ScalableResolutionProfile(ResolutionProfile):
    """
    根据当前窗口分辨率，将基准 1080p 布局按比例缩放后的配置。
    """

    def __init__(
        self,
        target_width: int,
        target_height: int,
        ref: ResolutionProfile | None = None,
    ) -> None:
        self._w = target_width
        self._h = target_height
        self._ref = ref if ref is not None else Resolution1080p()
        self._sx = target_width / _REF_W
        self._sy = target_height / _REF_H

    @property
    def RESOLUTION(self) -> tuple[int, int]:
        return (self._w, self._h)

    @property
    def essence_icon_x_list(self) -> Sequence[int]:
        base = self._ref.essence_icon_x_list
        return [round(x * self._sx) for x in base]

    @property
    def essence_icon_y_list(self) -> Sequence[int]:
        base = self._ref.essence_icon_y_list
        return [round(y * self._sy) for y in base]

    @property
    def ESSENCE_UI_ROI(self) -> Region:
        return _scale_region(self._ref.ESSENCE_UI_ROI, self._sx, self._sy)

    @property
    def AREA(self) -> Region:
        return _scale_region(self._ref.AREA, self._sx, self._sy)

    @property
    def DEPRECATE_BUTTON_POS(self) -> Point:
        return _scale_point(self._ref.DEPRECATE_BUTTON_POS, self._sx, self._sy)

    @property
    def LOCK_BUTTON_POS(self) -> Point:
        return _scale_point(self._ref.LOCK_BUTTON_POS, self._sx, self._sy)

    @property
    def DEPRECATE_BUTTON_ROI(self) -> Region:
        return _scale_region(self._ref.DEPRECATE_BUTTON_ROI, self._sx, self._sy)

    @property
    def LOCK_BUTTON_ROI(self) -> Region:
        return _scale_region(self._ref.LOCK_BUTTON_ROI, self._sx, self._sy)

    @property
    def STATS_0_ROI(self) -> Region:
        return _scale_region(self._ref.STATS_0_ROI, self._sx, self._sy)

    @property
    def STATS_1_ROI(self) -> Region:
        return _scale_region(self._ref.STATS_1_ROI, self._sx, self._sy)

    @property
    def STATS_2_ROI(self) -> Region:
        return _scale_region(self._ref.STATS_2_ROI, self._sx, self._sy)

    @property
    def MASK_ESSENCE_REGION_UID(self) -> Region:
        return _scale_region(self._ref.MASK_ESSENCE_REGION_UID, self._sx, self._sy)

    @property
    def MASK_ESSENCE_REGION_CURRENCY(self) -> Region:
        return _scale_region(self._ref.MASK_ESSENCE_REGION_CURRENCY, self._sx, self._sy)

    @property
    def stats_level_icon_points(self) -> list[Sequence[Point]]:
        base = self._ref.stats_level_icon_points
        return [
            [_scale_point(p, self._sx, self._sy) for p in row]
            for row in base
        ]
