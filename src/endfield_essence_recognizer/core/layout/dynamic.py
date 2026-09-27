"""
动态分辨率布局模块。

配合 ``ScalingImageSource`` 使用：
- 宽比例 (>= 16:9)：匹配标准高度 1080（按高缩放），宽度 >= 1920
- 窄比例 (< 16:9)：匹配标准宽度 1920（按宽缩放），高度 > 1080

根据缩放后的逻辑尺寸，动态计算所有坐标和区域。

布局规律（截图验证）：
- 右侧属性面板：宽度和右边距固定，基于右边缘锚定
- 左侧物品网格：自适应卡片式布局，列数根据可用宽度动态计算，居中排列
- Y 坐标：直接使用 1080p 值（高度已归一化）

可使用 ``scripts/test_layout_anchoring.py`` 对不同分辨率截图进行可视化验证。
"""

import math
from collections.abc import Sequence

from endfield_essence_recognizer.utils.log import logger

from .base import Point, Region, ResolutionProfile
from .res_1080p import Resolution1080p

_BASE = Resolution1080p()
_BASE_WIDTH = 1920
_BASE_HEIGHT = 1080

# 物品网格卡片参数（1080p 高度下的固定值）
_CARD_SIZE = 145
"""基质卡片的边长，用于取半进行点击位置计算"""
_SPACING_W = 155.4
"""基质网格的水平间距"""
_SPACING_H = 155.1
"""基质网格的竖直间距"""
_FIRST_Y = 130
"""第一个卡片左上角 Y"""
_CONTAINER_LEFT = 38
"""网格容器左边界 X 坐标"""
_BOTTOM_MARGIN = 120
"""网格容器底部边距（距逻辑高度底边）"""

# 右侧面板距右边缘的距离
_PANEL_RIGHT_MARGIN = _BASE_WIDTH - _BASE.AREA.x0  # 455

# 滚动条检测点距窗口右/下/上边缘的距离（逻辑坐标系下恒定，由 1080p 基准值推导）
_SCROLLBAR_RIGHT_MARGIN = _BASE_WIDTH - _BASE.SCROLLBAR_CHECK_POS.x  # 467
_SCROLLBAR_BOTTOM_MARGIN = _BASE_HEIGHT - _BASE.SCROLLBAR_CHECK_POS.y  # 130
_SCROLLBAR_TOP_MARGIN = _BASE.SCROLLBAR_TOP_CHECK_POS.y  # 130


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

    接收 ``ScalingImageSource`` 输出的逻辑分辨率，动态计算所有坐标：

    - 右侧面板元素：基于右边距锚定（距右边缘距离不变）
    - 左侧物品网格：根据可用宽度计算列数，卡片居中排列
    - 左侧固定元素（场景检测 ROI、UID 遮罩等）：坐标不变

    在 16:9（1920x1080）下，所有坐标与 ``Resolution1080p`` 完全一致。

    布局计算方法：
    +-<A>------------------------+-<B>---------+
    |                            *----const----*
    |       <C>                  |             |
    |    P--+-----+-----+-----+--R             |
    |       |  S              |  |             |
    |       +     +     +     +  |             |
    |       |                 |  |             |
    |       +     +     +     +  |             |
    |       |                 |  |             |
    |       +-----+-----+-----+  |             |
    |       |                    |             |
    |       Q                    |             |
    +----------------------------+-------------+

    - <A> 左侧固定元素
      - 场景检测 ROI、UID 遮罩等
      - 逻辑坐标与标准 1080p 坐标完全一致
    - <B> 右侧面板元素
      - 属性面板区域、按钮、统计图标等
      - 基于右边距锚定（距右边缘距离不变）
    - <C> 左侧基质网格
      - 根据可用宽高计算列数和行数，卡片居中排列
    关键坐标：
    - P-R 的 x 表示网格容器的上边缘跨度，由 `_CONTAINER_LEFT` 和 `_PANEL_RIGHT_MARGIN` 定义
    - P-R 整除 `_SPACING_W` 得到列数，剩余空间平均分布在两侧实现居中。进而计算每列图标的 x 点击坐标列表。
    - Q 的 y 表示网格容器的下边缘，由 `_BOTTOM_MARGIN` 定义。
    - 根据 Q 和 P 的 y 以及 `_SPACING_H` 计算能够完整显示的行数，进而计算每行图标的 y 点击坐标列表。

    Args:
        logical_width: 窗口的逻辑宽度。
        logical_height: 窗口的逻辑高度。

    注：传入的逻辑分辨率应当满足`compute_logical_size`函数的缩放，即
    (1)宽=1920时高>1080，或(2)高=1080时宽>=1920，否则计算出的布局可能无实际意义。
    """

    def __init__(self, logical_width: int, logical_height: int = 1080) -> None:
        self._width = logical_width
        self._height = logical_height

        # 计算自适应网格
        container_right = self._width - _PANEL_RIGHT_MARGIN
        container_width = container_right - _CONTAINER_LEFT
        self._grid_cols = math.floor(container_width / _SPACING_W)
        first_x = round(
            _CONTAINER_LEFT + (container_width - self._grid_cols * _SPACING_W) / 2
        )

        self._icon_x = [
            round(first_x + _CARD_SIZE // 2 + i * _SPACING_W)
            for i in range(self._grid_cols)
        ]
        # 计算自适应行数
        usable_bottom = self._height - _BOTTOM_MARGIN
        self._grid_rows = max(
            1, int((usable_bottom - _FIRST_Y - _CARD_SIZE) / _SPACING_H) + 1
        )

        self._icon_y = [
            round(_FIRST_Y + _CARD_SIZE // 2 + i * _SPACING_H)
            for i in range(self._grid_rows)
        ]

        logger.info(
            f"DynamicResolutionProfile: {logical_width}x{logical_height}, "
            f"grid={self._grid_cols}x{self._grid_rows}"
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
    def RARITY_ROI(self) -> Region:
        return self._ra_region(_BASE.RARITY_ROI)

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

    # 拖拽翻页配置 - Y坐标根据高度比例缩放

    @property
    def DRAG_START_POS(self) -> Point:
        base = _BASE.DRAG_START_POS
        return Point(base.x, round(base.y * self._height / _BASE_HEIGHT))

    @property
    def DRAG_END_POS(self) -> Point:
        base = _BASE.DRAG_END_POS
        return Point(base.x, round(base.y * self._height / _BASE_HEIGHT))

    @property
    def SCROLLBAR_CHECK_POS(self) -> Point:
        """滚动条检测位置，用于判断是否到达底部。

        滚动条在逻辑坐标系下基于窗口右下角恒定锚定，边距不随逻辑高度变化：
        - 右边距 467：与右侧面板（右锚定 455）属于同一套锚定规律
        - 下边距 130：与网格容器底部边距（120）一样是逻辑常量

        注意：**不能**按下边距 × 逻辑高度/1080 缩放。逻辑高度 > 1080 的窄比例
        分辨率（16:10 / 3:2 / 4:3 / 5:4）下，按高度放大会让检测点向左上方漂移
        进基质网格内部，被卡片边缘/稀有度色条的亮点误触发，提前判定“已到底”。

        实测数据：
        - 1920×1080（逻辑 1920×1080）→ (1453, 950)：右距 467、下距 130
        - 2560×1080（逻辑 2560×1080）→ (2093, 950)：右距 467、下距 130
        - 2560×1600（逻辑 1920×1200）→ (1453, 1070)：反算物理 (1937, 1427)，
          与实测滚动条位置 (1934, 1430) 一致（旧公式为逻辑 (1401, 1056)）
        """
        return Point(
            self._width - _SCROLLBAR_RIGHT_MARGIN,
            self._height - _SCROLLBAR_BOTTOM_MARGIN,
        )

    @property
    def SCROLLBAR_TOP_CHECK_POS(self) -> Point:
        """滚动条顶部检测位置，用于判断是否回到第一页。

        与行末检测（SCROLLBAR_CHECK_POS）共用同一套右下锚定律：右边距 467 恒定。
        顶部边距 130 同样恒定——网格首行锚定在逻辑 y=130，不随逻辑高度变化。
        """
        return Point(self._width - _SCROLLBAR_RIGHT_MARGIN, _SCROLLBAR_TOP_MARGIN)
