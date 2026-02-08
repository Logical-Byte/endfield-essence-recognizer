"""
基于基准 1080p 布局按比例缩放到任意分辨率的配置。

基准坐标，通过 (target_w / 1920, target_h / 1080) 缩放计算得到
"""

from collections.abc import Sequence

from .base import Point, Region, ResolutionProfile
from .res_1080p import Resolution1080p

_REF_W = 1920
_REF_H = 1080
# 缩放方案基于 16:9 基准，仅支持 16:9 分辨率
_ASPECT_W = 16
_ASPECT_H = 9


def _scale_point(p: Point, sx: float, sy: float) -> Point:
    return Point(round(p.x * sx), round(p.y * sy))


def _scale_region(r: Region, sx: float, sy: float) -> Region:
    return Region(_scale_point(r.p0, sx, sy), _scale_point(r.p1, sx, sy))


class ScalableResolutionProfile(ResolutionProfile):
    """
    根据当前窗口分辨率，将基准 1080p 布局按比例缩放后的配置。

    仅支持 16:9 分辨率；非 16:9 会导致缩放比例不一致，布局会失真。
    """

    def __init__(
        self,
        target_width: int,
        target_height: int,
        ref: ResolutionProfile | None = None,
    ) -> None:
        if target_width <= 0 or target_height <= 0:
            raise ValueError(
                f"分辨率宽高须为正整数，得到 {target_width}x{target_height}"
            )
        if _ASPECT_W * target_height != _ASPECT_H * target_width:
            raise ValueError(
                f"ScalableResolutionProfile 仅支持 16:9 分辨率，"
                f"得到 {target_width}x{target_height}（比例 {target_width / target_height:.4f}，非 16/9≈{16 / 9:.4f}）"
            )
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
    def STATS_LEVEL_ICON_POINTS(self) -> list[list[Point]]:
        base = self._ref.STATS_LEVEL_ICON_POINTS
        return [[_scale_point(p, self._sx, self._sy) for p in row] for row in base]

    @property
    def LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI(self) -> Region:
        return _scale_region(
            self._ref.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI, self._sx, self._sy
        )

    @property
    def DELIVERY_JOB_REWARD_ROI(self) -> Region:
        return _scale_region(self._ref.DELIVERY_JOB_REWARD_ROI, self._sx, self._sy)

    @property
    def DELIVERY_JOB_REFRESH_BUTTON_POINT(self) -> Point:
        return _scale_point(
            self._ref.DELIVERY_JOB_REFRESH_BUTTON_POINT, self._sx, self._sy
        )
