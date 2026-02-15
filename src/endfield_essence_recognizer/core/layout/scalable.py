"""
基于基准 1080p 布局按比例缩放到任意分辨率的配置。

基准坐标，通过 (target_w / 1920, target_h / 1080) 缩放计算得到
"""

from collections.abc import Sequence
from fractions import Fraction

from .base import Point, Region, ResolutionProfile


def _scale_point(p: Point, sx: float, sy: float) -> Point:
    return Point(round(p.x * sx), round(p.y * sy))


def _scale_region(r: Region, sx: float, sy: float) -> Region:
    return Region(_scale_point(r.p0, sx, sy), _scale_point(r.p1, sx, sy))


class ScalableResolutionProfile(ResolutionProfile):
    """
    Takes a reference ResolutionProfile and scales its coordinates
    to mimic a target resolution profile.

    Note:
        This class only handles calculations based on scaling factors.
        It does not validate whether the ratio of the `ref` is supported
        by the app.

    Args:
        target_width (int): 目标分辨率宽度，须为正整数
        target_height (int): 目标分辨率高度，须为正整数
        ref (ResolutionProfile): 用于缩放的基准分辨率配置
    Raises:
        ValueError: 如果目标分辨率宽高非正整数，或比例不符合 ref 的比例
    """

    def __init__(
        self,
        target_width: int,
        target_height: int,
        ref: ResolutionProfile,
    ) -> None:
        if target_width <= 0 or target_height <= 0:
            raise ValueError(
                f"分辨率宽高须为正整数，得到 {target_width}x{target_height}"
            )
        if Fraction(target_width, target_height) != Fraction(
            ref.RESOLUTION[0], ref.RESOLUTION[1]
        ):
            raise ValueError(
                f"仅支持与基准分辨率比例相同的分辨率，"
                f"基准分辨率比例为 "
                f"{ref.RESOLUTION[0]}:{ref.RESOLUTION[1]}，"
                f"得到 {target_width}:{target_height}"
            )
        self._w = target_width
        self._h = target_height
        self._ref = ref
        self._sx = self._w / self._ref.RESOLUTION[0]
        self._sy = self._h / self._ref.RESOLUTION[1]

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
    def RARITY_ROI(self) -> Region:
        return _scale_region(self._ref.RARITY_ROI, self._sx, self._sy)

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
