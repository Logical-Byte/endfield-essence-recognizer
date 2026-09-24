"""未点开卡片上的"已操作标记"检测（锁定 / 弃用）。

扫描前预判：用户已经处理过的卡片会在卡片左下角留下状态角标 —— 锁定（保留）
或弃用（作为养成材料）。两种角标出现在**同一个位置**，因此共用同一个搜索窗，
对每个标记模板分别做模板匹配。任一模板命中即认为该格已被用户决定过，
用于跳过"点击 → 整屏识别"的完整流程。它只省时间，不改变任何判定语义。

为何没有复用 ``TemplateRecognizer``
----------------------------------
1. 未命中是**常态**（一页里多数卡片没有任何标记），而 ``TemplateRecognizer``
   在分数低于阈值时会逐次 ``logger.warning``；直接复用会让每次扫描刷出上百条告警。
2. 这里的高低阈值按本场景实测标定（见 ``_HIGH_THRESHOLD``），与面板图标识别
   所用的 0.75 / 0.50 不是一个量级，沿用会全部落空。
3. 面板上的"已锁定 / 未锁定"按钮图标与卡片角标是**两种不同的渲染**
   （面板图标是深底白锁、高对比；卡片角标是亮底淡色描边、低对比），
   实测互相替代的匹配分数比噪声还低，因此必须使用从截图裁出的专用模板。

因此本模块只做检测（返回分数），阈值判断与日志由调用方决定。
"""

from __future__ import annotations

import importlib.resources
from enum import StrEnum
from typing import TYPE_CHECKING

import cv2

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.utils.image import load_image, to_gray_image
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cv2.typing import MatLike


class SkipMarkerLabel(StrEnum):
    """卡片上的"已操作标记"类型（都表示用户已经对这张卡片做出决定）。"""

    LOCKED = "已锁定"
    """锁定 = 决定保留。"""

    DEPRECATED = "已弃用"
    """弃用 = 作为养成材料。"""


#: 卡片状态标记模板（均从 2560x1080 截图裁出，20x20）。
#: 锁定与弃用角标渲染在卡片的同一位置，所以共用下面的搜索窗。
_MARKER_TEMPLATES: tuple[tuple[str, SkipMarkerLabel], ...] = (
    ("卡片锁定标记.png", SkipMarkerLabel.LOCKED),
    ("卡片弃用标记.png", SkipMarkerLabel.DEPRECATED),
)

#: 角标搜索窗相对格子点击坐标（``essence_icon_x_list`` / ``essence_icon_y_list``
#: 的元素）的偏移与尺寸。
#: 实测（2560x1080）：锁定角标左上角落在 dx∈[-70, -67]、dy∈[46, 47]；
#: 弃用角标落在 dx=-68、dy=47，即两者位置一致，跨度不超过 3px x 1px。
#: 窗口在四个方向各留约 10px 余量，用于容纳不同分辨率下网格取整与格距累积
#: 带来的漂移（2560 宽下 13 列累计约 3px）。
#: 窗口远小于 155px 的格距，不会覆盖到相邻格子的角标。
_SEARCH_OFFSET_X = -80
_SEARCH_OFFSET_Y = 36
_SEARCH_WIDTH = 43
_SEARCH_HEIGHT = 41

#: 判定阈值，对两个标记模板通用。实测噪声底与信号之间的空档：
#: - 锁定标记：已锁定格最低 0.819，未标记格最高 0.350（有锁定标记的整页）
#:   与 0.361（无标记的整页）；
#: - 弃用标记：已弃用格最低 0.902，未标记格最高 0.130，且它在已锁定格上的
#:   交叉分数最高 0.395（不会把锁定格误判为弃用）。
#: 两侧信号都远高于 0.45，阈值从 0.45 扫到 0.70 结果不变。
_HIGH_THRESHOLD = 0.45

#: 越界格（翻页后顶部被裁切的半张卡片）的分数，即"无法判断"。
_UNDETERMINED_SCORE = -1.0


class SkipMarkerDetector:
    """检测未点开卡片上的"已操作"标记（锁定 / 弃用）。"""

    def __init__(self, name: str = "SkipMarkerDetector") -> None:
        self.name = name
        self._templates: list[tuple[SkipMarkerLabel, MatLike]] = []

    def __str__(self) -> str:
        return f"[{self.name}]"

    def load_templates(self) -> None:
        """从包资源加载全部标记模板。

        单个模板加载失败只记录错误并跳过它：本检测器在应用启动时构造，
        不能因为一张模板缺失就阻断启动。全部模板都失败时 ``loaded`` 为假，
        调用方会安全降级为"不做任何跳过"，只有部分失败时对应的那类标记
        不会被识别。
        """
        templates_dir = (
            importlib.resources.files("endfield_essence_recognizer")
            / "templates/screenshot"
        )
        loaded: list[tuple[SkipMarkerLabel, MatLike]] = []
        for filename, label in _MARKER_TEMPLATES:
            try:
                with importlib.resources.as_file(templates_dir / filename) as path:
                    image = load_image(path, cv2.IMREAD_GRAYSCALE)
                loaded.append((label, image))
            except Exception as e:
                logger.error(f"{self} 加载标记模板失败 {filename}: {e}")
        self._templates = loaded

    @property
    def loaded(self) -> bool:
        """是否至少加载成功了一个标记模板。"""
        return bool(self._templates)

    @property
    def loaded_labels(self) -> set[SkipMarkerLabel]:
        """已成功加载模板的标记类型。"""
        return {label for label, _template in self._templates}

    def score_cell(
        self,
        frame: MatLike,
        center: Point,
        label: SkipMarkerLabel | None = None,
    ) -> float:
        """返回单个格子上标记模板的最高匹配分数。

        Args:
            frame: 整页截图（灰度或彩色均可）。
            center: 该格子的点击坐标（``essence_icon_*_list`` 元素）。
            label: 只比较该类型的模板；``None`` 表示比较全部模板。

        Returns:
            最高匹配分数；搜索窗越界（无法判断）时返回 ``_UNDETERMINED_SCORE``。
        """
        _label, best_score = self.score_cell_by_label(frame, center, label)
        return best_score

    def score_cell_by_label(
        self,
        frame: MatLike,
        center: Point,
        label: SkipMarkerLabel | None = None,
    ) -> tuple[SkipMarkerLabel | None, float]:
        """返回 ``(分数最高的标记类型, 该分数)``。

        Args:
            frame: 整页截图。
            center: 该格子的点击坐标。
            label: 只比较该类型的模板；``None`` 表示比较全部模板。

        Returns:
            没有任何模板可比（未加载或搜索窗越界）时返回 ``(None, _UNDETERMINED_SCORE)``。
        """
        x0 = center.x + _SEARCH_OFFSET_X
        y0 = center.y + _SEARCH_OFFSET_Y
        # 负索引会从图像末尾反向切片，取到无关像素；必须显式拒绝越界窗口
        if (
            x0 < 0
            or y0 < 0
            or x0 + _SEARCH_WIDTH > frame.shape[1]
            or y0 + _SEARCH_HEIGHT > frame.shape[0]
        ):
            return None, _UNDETERMINED_SCORE
        patch = frame[y0 : y0 + _SEARCH_HEIGHT, x0 : x0 + _SEARCH_WIDTH]

        best_label: SkipMarkerLabel | None = None
        best_score = _UNDETERMINED_SCORE
        for template_label, template in self._templates:
            if label is not None and template_label is not label:
                continue
            template_height, template_width = template.shape[:2]
            if patch.shape[0] < template_height or patch.shape[1] < template_width:
                continue
            # matchTemplate 要求图像与模板 dtype 一致：模板为 uint8 灰度，这里统一。
            result = cv2.matchTemplate(
                to_gray_image(patch), template, cv2.TM_CCOEFF_NORMED
            )
            score = float(result.max())
            if score > best_score:
                best_score = score
                best_label = template_label
        return best_label, best_score

    def find_marked_cells(
        self,
        frame: MatLike,
        icon_x_list: Sequence[int],
        icon_y_list: Sequence[int],
    ) -> dict[tuple[int, int], SkipMarkerLabel]:
        """返回整页中带有"已操作"标记的格子及其标记类型。

        Args:
            frame: 整页截图。
            icon_x_list: 各列的点击 X 坐标。
            icon_y_list: 各行的点击 Y 坐标。

        Returns:
            ``{(row, col): 标记类型}``，行列 0 起算。模板未加载或分数处于
            模糊区间时，该格不会被计入，由调用方回退到"点击后识别"。
            两种角标位于同一位置，因此一格最多只会得到一个类型
            （取分数更高的那个模板）。
        """
        if not self._templates:
            return {}

        marked: dict[tuple[int, int], SkipMarkerLabel] = {}
        for row, icon_y in enumerate(icon_y_list):
            for col, icon_x in enumerate(icon_x_list):
                label, score = self.score_cell_by_label(frame, Point(icon_x, icon_y))
                if label is not None and score >= _HIGH_THRESHOLD:
                    marked[(row, col)] = label
        return marked
