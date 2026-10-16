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
#: 亮色“非亮点”干扰带的亮度。
#: 面板上真实存在的最亮非亮点像素是 195，绝对阈值 200 就能挡住它，所以要用 245
#: 才能落进“相对阈值能挡住、绝对阈值挡不住”的区间（本行最亮 254 时，相对阈值
#: 把判定线抬到 254 * 0.8 = 203，而 245 经 5x5 采样后恰好是 202）。
SELECTED_ROW_BAND_BRIGHTNESS = 245
#: 选中底色带相对标称亮点行的位置（实测新版 y≈504..520、x≈1512..1586）。
#: 高度取 4px：5x5 采样窗口只覆盖 4/5，采样值约为带亮度的 0.8 倍
SELECTED_ROW_BAND_TOP = 511
SELECTED_ROW_BAND_BOTTOM = 515
#: 选中底色带覆盖的 X 范围（全局坐标）
SELECTED_ROW_BAND_LEFT = 1523
SELECTED_ROW_BAND_RIGHT = 1586
#: 干扰带上的“暗”亮点下标：这些位置实际不画亮点，但会被干扰带采样到
SELECTED_ROW_LIT_INDICES = (0, 1, 2)

RESOLUTION_PROFILE = Resolution1080p()
POSITIONS = RESOLUTION_PROFILE.STATS_LEVEL_ICON_POINTS


def build_panel_with_selected_row_band() -> np.ndarray:
    """
    生成一张“第三行压在选中底色带上”的合成面板。

    第一、二行全亮，第三行只点亮 `SELECTED_ROW_LIT_INDICES`，其余位置不画亮点，
    但在它们所在的标称行上压一条高亮干扰带——模拟选中行的底色带亮到足以越过
    绝对阈值的情形。此时只有相对阈值能把这条带子挡在门外。

    Returns:
        与客户区截图同尺寸的 BGR 图像（1920x1080）。
    """
    image = np.full((PANEL_HEIGHT, PANEL_WIDTH, 3), PANEL_BACKGROUND, dtype=np.uint8)
    radius = DOT_DIAMETER // 2
    for stat_index in (0, 1):
        for nominal_point in POSITIONS[stat_index]:
            cv2.circle(
                image,
                (nominal_point.x, nominal_point.y),
                radius,
                (DOT_BRIGHTNESS,) * 3,
                -1,
            )
    image[
        SELECTED_ROW_BAND_TOP:SELECTED_ROW_BAND_BOTTOM,
        SELECTED_ROW_BAND_LEFT:SELECTED_ROW_BAND_RIGHT,
    ] = SELECTED_ROW_BAND_BRIGHTNESS
    # 干扰带画在标称行上，会盖住第三行亮点的下半部分，所以亮点要重画一遍
    for index in SELECTED_ROW_LIT_INDICES:
        nominal_point = POSITIONS[2][index]
        cv2.circle(
            image, (nominal_point.x, nominal_point.y), radius, (DOT_BRIGHTNESS,) * 3, -1
        )
    return image


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
    """暗点压在选中底色带上时（面板最亮的非亮点元素）不能被判成亮点。

    干扰带亮度落在“绝对阈值挡不住、相对阈值挡得住”的区间：去掉相对阈值时第三行的
    第四个暗点会被当成亮点，等级从 3 变成 4。因此这条断言同时锁住了两件事——暗点
    不算亮点，以及相对阈值确实在起作用。
    """
    assert recognize(build_panel_with_selected_row_band()) == [6, 6, 3]


def test_returns_none_when_the_whole_level_region_is_outside_the_image():
    # 窗口尺寸小于布局标称分辨率时，等级亮点区域可能整块落在画面外：
    # 此时应按识别失败处理，既不抛异常也不报警告
    assert recognize(np.full((400, 400, 3), PANEL_BACKGROUND, dtype=np.uint8)) == [
        None,
        None,
        None,
    ]


def test_returns_none_when_panel_is_blank():
    # 亮点区域在画面内、但一个亮点都没有时同样按识别失败处理
    blank = np.full((PANEL_HEIGHT, PANEL_WIDTH, 3), PANEL_BACKGROUND, dtype=np.uint8)
    assert recognize(blank) == [None, None, None]
