"""Unit tests for scaling adapters.

These tests focus on behavior that can silently regress:
- width/height-based logical scaling branch selection
- image scaling and ROI slicing consistency
- logical-to-physical click coordinate mapping
- construction-time validation for invalid capture sizes or scale factors

Why validate exceptional cases?
In practice, window capture or window state transitions can transiently report
invalid client sizes (for example 0x0 during restore/minimize races). Guarding
these inputs early prevents divide-by-zero and invalid coordinate mapping.
"""

import cv2
import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import Point, Region
from endfield_essence_recognizer.core.window.scaling import (
    ScalingImageSource,
    ScalingWindowActions,
    compute_logical_size,
    create_scaling_wrappers,
)


class MockImageSource:
    def __init__(self, image: np.ndarray) -> None:
        self._image = image

    def screenshot(self, relative_region: Region | None = None):
        if relative_region is None:
            return self._image
        p0, p1 = relative_region.p0, relative_region.p1
        return self._image[p0.y : p1.y, p0.x : p1.x]

    def get_client_size(self) -> tuple[int, int]:
        h, w = self._image.shape[:2]
        return w, h


class MockWindowActions:
    def __init__(self) -> None:
        self.clicked: list[tuple[int, int]] = []
        self.waited: list[float] = []
        self.target_exists = True
        self.target_is_active = False

    def restore(self) -> bool:
        return True

    def activate(self) -> bool:
        return True

    def show(self) -> bool:
        return True

    def click(self, relative_x: int, relative_y: int) -> None:
        self.clicked.append((relative_x, relative_y))

    def wait(self, seconds: float) -> None:
        self.waited.append(seconds)


def test_compute_logical_size_wide_and_narrow():
    """Verify both scaling branches and the 16:9 baseline contract.

    Value: protects the core branch logic (wide->height, narrow->width), which
    directly determines all downstream layout coordinates.
    """
    lw, lh, scale = compute_logical_size(1920, 1080)
    assert (lw, lh) == (1920, 1080)
    assert scale == pytest.approx(1.0)

    lw, lh, scale = compute_logical_size(2560, 1440)
    assert (lw, lh) == (1920, 1080)
    assert scale == pytest.approx(0.75)

    lw, lh, scale = compute_logical_size(1680, 1050)
    assert (lw, lh) == (1920, 1200)
    assert scale == pytest.approx(1920 / 1680)


@pytest.mark.parametrize(
    ("physical_width", "physical_height"),
    [
        (0, 1080),
        (1920, 0),
        (-1, 1080),
        (1920, -1),
    ],
)
def test_compute_logical_size_rejects_non_positive_inputs(
    physical_width: int,
    physical_height: int,
):
    """Reject invalid capture sizes early.

    Value: avoids divide-by-zero and undefined scaling when transient window
    states report 0 or negative client dimensions.
    """
    with pytest.raises(ValueError, match="must be positive"):
        compute_logical_size(physical_width, physical_height)


def test_scaling_image_source_full_and_region_screenshot():
    """Ensure screenshot scaling and logical ROI cropping remain consistent.

    Value: catches regressions in "scale first, then crop" behavior that would
    shift OCR/template ROIs and degrade recognition accuracy.
    """
    physical = np.arange(100 * 200 * 3, dtype=np.uint8).reshape((100, 200, 3))
    source = ScalingImageSource(MockImageSource(physical))

    assert source.physical_size == (200, 100)
    assert source.logical_size == (2160, 1080)
    assert source.get_client_size() == (2160, 1080)

    full_scaled = source.screenshot()
    assert full_scaled.shape == (1080, 2160, 3)

    region = Region(Point(120, 80), Point(320, 280))
    cropped = source.screenshot(region)
    assert cropped.shape == (200, 200, 3)

    expected = full_scaled[80:280, 120:320]
    assert np.array_equal(cropped, expected)


def test_scaling_window_actions_maps_coordinates_and_delegates():
    """Verify click coordinate back-mapping and action delegation.

    Value: this is the critical runtime path for interactions; wrong rounding or
    missing delegation would click wrong UI targets.
    """
    base_actions = MockWindowActions()
    actions = ScalingWindowActions(base_actions, scale_factor=0.8)

    assert actions.target_exists is True
    assert actions.target_is_active is False
    assert actions.restore() is True
    assert actions.activate() is True
    assert actions.show() is True

    actions.click(101, 51)
    assert base_actions.clicked == [(126, 64)]

    actions.wait(0.25)
    assert base_actions.waited == [0.25]


@pytest.mark.parametrize("scale_factor", [0.0, -1.0, float("inf"), float("nan")])
def test_scaling_window_actions_rejects_invalid_scale_factor(scale_factor: float):
    """Validate constructor guard for non-usable scale factors.

    Value: prevents creating an adapter that would produce invalid clicks or
    runtime math errors (e.g., divide-by-zero/NaN propagation).
    """
    with pytest.raises(ValueError, match="finite positive"):
        ScalingWindowActions(MockWindowActions(), scale_factor=scale_factor)


def test_create_scaling_wrappers_returns_consistent_pair():
    """Ensure factory keeps source/action wrappers scale-consistent.

    Value: prevents wiring drift in DI code where source and action adapters
    could accidentally use different scale assumptions.
    """
    physical = np.arange(1440 * 2560 * 3, dtype=np.uint8).reshape((1440, 2560, 3))
    source = MockImageSource(physical)
    base_actions = MockWindowActions()

    scaling_source, scaling_actions = create_scaling_wrappers(source, base_actions)

    assert scaling_source.scale_factor == pytest.approx(0.75)
    scaling_actions.click(300, 150)
    assert base_actions.clicked == [(400, 200)]

    full_scaled = scaling_source.screenshot()
    expected = cv2.resize(physical, (1920, 1080), interpolation=cv2.INTER_AREA)
    assert np.array_equal(full_scaled, expected)
