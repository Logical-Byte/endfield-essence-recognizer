"""
动态分辨率布局模块。

配合 ``ScalingImageSource`` 使用：图像已被缩放到 1080p 高度，宽度按原始宽高比
等比缩放。本模块根据缩放后的逻辑宽度，动态计算所有坐标和区域。

布局规律（经截图验证）：
- 右侧属性面板：宽度和右边距固定，基于右边缘锚定
- 左侧物品网格：自适应卡片式布局，列数根据可用宽度动态计算，居中排列
- Y 坐标：直接使用 1080p 值（高度已归一化）
"""

from collections.abc import Sequence

from endfield_essence_recognizer.utils.log import logger

from .base import Point, Region, ResolutionProfile
from .res_1080p import Resolution1080p

_BASE = Resolution1080p()
_BASE_WIDTH = 1920

# 物品网格卡片参数（1080p 高度下的固定值）
_CARD_SIZE = 145
_SPACING_W = 155.4  # 水平间距（左上角到左上角）
_SPACING_H = 155  # 垂直间距
_FIRST_Y = 130  # 第一个卡片左上角 Y
_CONTAINER_LEFT = 38  # 网格容器左边界

# 右侧面板距右边缘的距离
_PANEL_RIGHT_MARGIN = _BASE_WIDTH - _BASE.AREA.x0  # 455


def _right_anchor_x(base_x: int, width: int) -> int:
    """将 1080p 基准 X 坐标按右边距映射到目标宽度。"""
    return width - (_BASE_WIDTH - base_x)


def _right_anchor_point(p: Point, width: int) -> Point:
    return Point(_right_anchor_x(p.x, width), p.y)


def _right_anchor_region(r: Region, width: int) -> Region:
    return Region(
        _right_anchor_point(r.p0, width),
        _right_anchor_point(r.p1, width),
    )


class DynamicResolutionProfile(ResolutionProfile):
    """
    动态分辨率布局配置。

    接收 ``ScalingImageSource`` 输出的逻辑分辨率（高度固定 1080，宽度按比例变化），
    动态计算所有坐标：

    - 右侧面板元素：基于右边距锚定（距右边缘距离不变）
    - 左侧物品网格：根据可用宽度计算列数，卡片居中排列
    - 左侧固定元素（场景检测 ROI、UID 遮罩等）：坐标不变

    在 16:9（1920x1080）下，所有坐标与 ``Resolution1080p`` 完全一致。
    """

    def __init__(self, logical_width: int, logical_height: int = 1080) -> None:
        self._width = logical_width
        self._height = logical_height

        # 计算自适应网格
        container_right = self._width - _PANEL_RIGHT_MARGIN
        container_width = container_right - _CONTAINER_LEFT
        self._grid_cols = int(container_width / _SPACING_W)
        first_x = round(
            _CONTAINER_LEFT + (container_width - self._grid_cols * _SPACING_W) / 2
        )

        self._icon_x = [
            round(first_x + _CARD_SIZE // 2 + i * _SPACING_W)
            for i in range(self._grid_cols)
        ]
        self._icon_y = [
            round(_FIRST_Y + _CARD_SIZE // 2 + i * _SPACING_H) for i in range(5)
        ]

        logger.info(
            f"DynamicResolutionProfile: {logical_width}x{logical_height}, "
            f"grid_cols={self._grid_cols}"
        )

    # --- helpers ---

    def _ra_point(self, p: Point) -> Point:
        return _right_anchor_point(p, self._width)

    def _ra_region(self, r: Region) -> Region:
        return _right_anchor_region(r, self._width)

    # --- ResolutionProfile implementation ---

    @property
    def RESOLUTION(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def essence_icon_x_list(self) -> Sequence[int]:
        return self._icon_x

    @property
    def essence_icon_y_list(self) -> Sequence[int]:
        return self._icon_y

    # 左侧固定元素 — 坐标不变

    @property
    def ESSENCE_UI_ROI(self) -> Region:
        return _BASE.ESSENCE_UI_ROI

    @property
    def MASK_ESSENCE_REGION_UID(self) -> Region:
        return _BASE.MASK_ESSENCE_REGION_UID

    @property
    def LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI(self) -> Region:
        return _BASE.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI

    # 右侧面板元素 — 右锚定

    @property
    def AREA(self) -> Region:
        return self._ra_region(_BASE.AREA)

    @property
    def DEPRECATE_BUTTON_POS(self) -> Point:
        return self._ra_point(_BASE.DEPRECATE_BUTTON_POS)

    @property
    def LOCK_BUTTON_POS(self) -> Point:
        return self._ra_point(_BASE.LOCK_BUTTON_POS)

    @property
    def DEPRECATE_BUTTON_ROI(self) -> Region:
        return self._ra_region(_BASE.DEPRECATE_BUTTON_ROI)

    @property
    def LOCK_BUTTON_ROI(self) -> Region:
        return self._ra_region(_BASE.LOCK_BUTTON_ROI)

    @property
    def STATS_0_ROI(self) -> Region:
        return self._ra_region(_BASE.STATS_0_ROI)

    @property
    def STATS_1_ROI(self) -> Region:
        return self._ra_region(_BASE.STATS_1_ROI)

    @property
    def STATS_2_ROI(self) -> Region:
        return self._ra_region(_BASE.STATS_2_ROI)

    @property
    def MASK_ESSENCE_REGION_CURRENCY(self) -> Region:
        return self._ra_region(_BASE.MASK_ESSENCE_REGION_CURRENCY)

    @property
    def STATS_LEVEL_ICON_POINTS(self) -> list[list[Point]]:
        return [
            [self._ra_point(p) for p in row] for row in _BASE.STATS_LEVEL_ICON_POINTS
        ]

    @property
    def DELIVERY_JOB_REWARD_ROI(self) -> Region:
        return self._ra_region(_BASE.DELIVERY_JOB_REWARD_ROI)

    @property
    def DELIVERY_JOB_REFRESH_BUTTON_POINT(self) -> Point:
        return self._ra_point(_BASE.DELIVERY_JOB_REFRESH_BUTTON_POINT)
