"""滚动条亮点检测的回归测试。

覆盖检测框几何（横向 ±4、纵向 ±2 的逻辑像素容差）与亮点判定阈值，
并锁定 2560×1600（逻辑 1920×1200）下实测亮区位于 1080p 标定值左侧约
3 像素时仍能被检出的行为。
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.scanner.engine import DraggableScannerEngine
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

# 2560×1600 的逻辑分辨率：底部检测点由 1080p 标定边距推导
_LOGICAL_WIDTH = 1920
_LOGICAL_HEIGHT = 1200
_BOTTOM_CHECK_POS = Point(1453, 1070)
_TOP_CHECK_POS = Point(1453, 130)


class _StubImageSource:
    """整窗黑底截图桩：支持按逻辑区域裁剪与放置亮点。"""

    def __init__(self, width: int = _LOGICAL_WIDTH, height: int = _LOGICAL_HEIGHT):
        self._image = np.zeros((height, width, 3), dtype=np.uint8)
        self.requested_regions: list[Region | None] = []

    def get_client_size(self) -> tuple[int, int]:
        return self._image.shape[1], self._image.shape[0]

    def set_pixel(self, x: int, y: int, bgr: tuple[int, int, int]) -> None:
        self._image[y, x] = bgr

    def screenshot(self, relative_region: Region | None = None) -> np.ndarray:
        self.requested_regions.append(relative_region)
        if relative_region is None:
            return self._image
        return self._image[
            relative_region.y0 : relative_region.y1,
            relative_region.x0 : relative_region.x1,
        ]


def _build_engine(image_source: _StubImageSource) -> DraggableScannerEngine:
    profile = MagicMock(spec=ResolutionProfile)
    profile.SCROLLBAR_CHECK_POS = _BOTTOM_CHECK_POS
    profile.SCROLLBAR_TOP_CHECK_POS = _TOP_CHECK_POS
    return DraggableScannerEngine(
        ctx=MagicMock(),
        image_source=image_source,
        window_actions=MagicMock(),
        user_setting_manager=MagicMock(spec=UserSettingManager),
        profile=profile,
    )


class TestScrollbarCheckRoi:
    def test_bottom_roi_spans_horizontal_tolerance(self):
        image_source = _StubImageSource()
        engine = _build_engine(image_source)

        engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS)

        assert image_source.requested_regions == [
            Region(Point(1449, 1068), Point(1458, 1073))
        ]

    def test_top_roi_uses_same_box(self):
        image_source = _StubImageSource()
        engine = _build_engine(image_source)

        engine._check_scrollbar_at_top()

        assert image_source.requested_regions == [
            Region(Point(1449, 128), Point(1458, 133))
        ]


class TestScrollbarBrightnessDetection:
    def test_calibrated_center_is_detected(self):
        image_source = _StubImageSource()
        image_source.set_pixel(1453, 1070, (255, 255, 255))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is True

    def test_measured_position_left_of_calibration_is_detected(self):
        # issue 实测亮区约在 (1450, 1072)：横向容差必须覆盖它
        image_source = _StubImageSource()
        image_source.set_pixel(1450, 1072, (200, 200, 200))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is True

    def test_leftmost_column_of_roi_is_detected(self):
        image_source = _StubImageSource()
        image_source.set_pixel(1449, 1070, (120, 120, 120))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is True

    @pytest.mark.parametrize(
        ("x", "y"),
        [
            (1448, 1070),  # 检测框左侧一列
            (1458, 1070),  # 检测框右侧一列
            (1453, 1067),  # 检测框上方一行
            (1453, 1073),  # 检测框下方一行
        ],
    )
    def test_bright_pixel_outside_roi_is_ignored(self, x: int, y: int):
        image_source = _StubImageSource()
        image_source.set_pixel(x, y, (255, 255, 255))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is False

    def test_dark_region_is_not_detected(self):
        engine = _build_engine(_StubImageSource())

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is False

    @pytest.mark.parametrize(
        ("bgr", "expected"),
        [
            ((101, 101, 101), True),
            ((100, 100, 100), False),  # 严格大于 100
            ((255, 255, 100), False),  # 三通道需同时高于 100
        ],
    )
    def test_requires_all_channels_above_threshold(
        self, bgr: tuple[int, int, int], expected: bool
    ):
        image_source = _StubImageSource()
        image_source.set_pixel(1453, 1070, bgr)
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is expected

    def test_top_check_detects_bright_pixel(self):
        image_source = _StubImageSource()
        image_source.set_pixel(1450, 130, (255, 255, 255))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_top() is True

    def test_screenshot_failure_returns_false(self):
        image_source = _StubImageSource()
        image_source.screenshot = MagicMock(side_effect=RuntimeError("截图失败"))
        engine = _build_engine(image_source)

        assert engine._check_scrollbar_at_bottom(_BOTTOM_CHECK_POS) is False
        assert engine._check_scrollbar_at_top() is False
