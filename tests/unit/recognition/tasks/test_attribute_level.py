"""等级亮点识别测试。

亮点坐标是“标称值”：游戏 UI 改版会让它相对实际亮点整体偏移若干像素
（实测新版比旧版下移约 3.4px，两版相对标称坐标分别漂移 -1.5px 与 +2.4px）
这里的合成面板用于锁定“偏移后仍能识别”这一行为。
"""

import cv2
import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.recognition.tasks.attribute_level import (
    AttributeLevelRecognizer,
    build_attribute_level_recognizer_profile,
)

PANEL_HEIGHT = 1080
PANEL_WIDTH = 1920

#: 亮点直径（实测旧版 15px、新版 16px）
DOT_DIAMETER = 15
#: 纯白高光的中心亮度（实测 254）
DOT_BRIGHTNESS = 254
#: 面板底色：低于识别阈值，避免暗点被误判为亮点
PANEL_BACKGROUND = 30
#: 三行词条下方的选中底色带亮度（实测约 131）：面板上最亮的“非亮点”元素，
#: 用于验证暗点压在这条底色带上时仍然不会被当成亮点
SELECTED_ROW_BAND_BRIGHTNESS = 131
#: 选中底色带相对标称亮点行的位置（实测新版 y≈504..520、x≈1512..1586）
SELECTED_ROW_BAND_TOP = 504
SELECTED_ROW_BAND_BOTTOM = 520

RESOLUTION_PROFILE = Resolution1080p()
POSITIONS = RESOLUTION_PROFILE.STATS_LEVEL_ICON_POINTS


def build_panel(
    levels: tuple[int, int, int], offset: Point = Point(0, 0)
) -> np.ndarray:
    """
    生成一张只包含三行等级亮点的合成面板。

    Args:
        levels: 三行词条各自的等级（0 表示该行没有任何亮点）。
        offset: 整组亮点相对标称坐标的偏移。

    Returns:
        与客户区截图同尺寸的 BGR 图像（1920x1080）。
    """
    image = np.full((PANEL_HEIGHT, PANEL_WIDTH, 3), PANEL_BACKGROUND, dtype=np.uint8)
    radius = DOT_DIAMETER // 2
    for stat_index, level in enumerate(levels):
        for nominal_point in POSITIONS[stat_index][:level]:
            center = (nominal_point.x + offset.x, nominal_point.y + offset.y)
            cv2.circle(image, center, radius, (DOT_BRIGHTNESS,) * 3, -1)
    return image


def recognize(image: np.ndarray) -> list[int | None]:
    recognizer = AttributeLevelRecognizer(
        "AttributeLevelRecognizer", build_attribute_level_recognizer_profile()
    )
    return [
        recognizer.recognize_level(image, stat_index, RESOLUTION_PROFILE)
        for stat_index in range(3)
    ]


def test_reads_levels_at_nominal_positions():
    assert recognize(build_panel((6, 2, 1))) == [6, 2, 1]


def test_returns_none_when_no_dot_is_lit():
    # 全暗时返回 None，而不是把背景噪声当成 +1
    assert recognize(build_panel((0, 0, 0))) == [None, None, None]


@pytest.mark.parametrize("offset", [-4, -3, -1, 0, 1, 3, 4])
def test_tolerates_vertical_drift(offset):
    """新旧版的差异就是整行下移 3~4px，这里覆盖更宽的垂直漂移。"""
    assert recognize(build_panel((6, 6, 3), Point(0, offset))) == [6, 6, 3]


@pytest.mark.parametrize("offset", [-4, -3, -1, 0, 1, 3, 4])
def test_tolerates_horizontal_drift(offset):
    assert recognize(build_panel((6, 6, 3), Point(offset, 0))) == [6, 6, 3]


@pytest.mark.parametrize(
    "offset", [Point(-4, -4), Point(4, 4), Point(-4, 4), Point(4, -4)]
)
def test_tolerates_diagonal_drift(offset):
    assert recognize(build_panel((6, 6, 3), offset)) == [6, 6, 3]


def test_stops_counting_at_first_dark_dot():
    # 计满 6 个亮点才算 +6，不能把相隔较远的亮点也算进来
    assert recognize(build_panel((6, 0, 0)))[0] == 6
    assert recognize(build_panel((1, 0, 0)))[0] == 1


def test_does_not_require_the_real_screenshot_to_be_1920x1080():
    # 窄比例分辨率下逻辑高度大于 1080，亮点面板仍位于顶部同一位置
    image = np.full((1200, PANEL_WIDTH, 3), PANEL_BACKGROUND, dtype=np.uint8)
    for nominal_point in POSITIONS[0]:
        cv2.circle(
            image,
            (nominal_point.x, nominal_point.y),
            DOT_DIAMETER // 2,
            (DOT_BRIGHTNESS,) * 3,
            -1,
        )
    assert recognize(image)[0] == 6


def test_dark_dot_on_selected_row_band_is_not_active():
    """暗点压在选中底色带上时（面板最亮的非亮点元素）不能被判成亮点。"""
    image = build_panel((6, 6, 3))
    band_left = POSITIONS[2][1].x - 8
    band_right = POSITIONS[2][5].x - 2
    image[
        SELECTED_ROW_BAND_TOP:SELECTED_ROW_BAND_BOTTOM,
        band_left:band_right,
    ] = SELECTED_ROW_BAND_BRIGHTNESS
    # 重画第 3 行的亮点，保证亮点依然亮于底色带
    radius = DOT_DIAMETER // 2
    for nominal_point in POSITIONS[2][:3]:
        cv2.circle(
            image,
            (nominal_point.x, nominal_point.y),
            radius,
            (DOT_BRIGHTNESS,) * 3,
            -1,
        )
    assert recognize(image) == [6, 6, 3]


def test_handles_dots_far_outside_the_image():
    # 亮点完全不在画面内时不应抛出异常，按识别失败处理
    empty = np.full((PANEL_HEIGHT, PANEL_WIDTH, 3), PANEL_BACKGROUND, dtype=np.uint8)
    assert recognize(empty) == [None, None, None]
