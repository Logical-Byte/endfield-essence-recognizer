"""属性词条文字识别测试。

在 1.5、1.6 两个版本中 UI 的三条中文词条都能正确识别；
`STATS_*_ROI` 给文字留了足够的上下余量 —— 模板匹配本身与文字在区域内的位置
无关，但只要文字被区域边界切掉就会掉分，所以余量就是"还能容忍 UI 再漂移多少"
"""

import cv2
import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.path import get_root_dir
from endfield_essence_recognizer.core.recognition.tasks.attribute import (
    build_attribute_profile,
)
from endfield_essence_recognizer.core.recognition.template_recognizer import (
    TemplateRecognizer,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData

pytestmark = [
    pytest.mark.skip_in_ci(
        reason="依赖 resources/data/v2 下的 json 与根目录截图，CI 环境不包含这些文件。"
    )
]

#: (截图, 词条序号) -> (期望的 stat id, 期望的中文名)
EXPECTED: dict[tuple[str, int], tuple[str, str]] = {
    ("旧版", 0): ("gat_passive_attr_will", "意志提升"),
    ("旧版", 1): ("gat_passive_attr_atk", "攻击提升"),
    ("旧版", 2): ("gst_passive_tacafter", "流转"),
    ("新版", 0): ("gat_passive_attr_will", "意志提升"),
    ("新版", 1): ("gat_passive_attr_hp", "生命提升"),
    ("新版", 2): ("gst_passive_keyword", "效益"),
}

SCREENSHOTS = {
    "旧版": "2026-10-16 旧版基质.png",
    "新版": "2026-10-16 新版基质.png",
}

#: 模板匹配的置信阈值，与 `build_attribute_profile` 的 high_threshold 一致
HIGH_THRESHOLD = 0.75
#: 实测匹配分数在 0.87~0.94，留一条下限用于发现识别质量悄悄退化
MIN_ACCEPTABLE_SCORE = 0.85
#: 两版文字并集的高度（实测 363~386）
TEXT_HEIGHT = 24
#: 允许的整体漂移量（逻辑像素）。
#: 区域在文字上方留 6px、下方留 15px（实测，见 `STATS_0_ROI` 的 docstring），
#: 能容忍的漂移由较小的一侧决定；实测再漂移 4px 时匹配仍满分行（0.87~0.94），
#: 到 5px 时文字边缘被切掉、分数才掉到阈值以下，故这里按 4px 断言。
DRIFT_TOLERANCE = 4

PROFILE = Resolution1080p()


def _screenshot_path(name: str):
    return get_root_dir() / SCREENSHOTS[name]


def _load(name: str) -> np.ndarray:
    path = _screenshot_path(name)
    if not path.exists():
        pytest.skip(f"缺少实拍截图 {path}")
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None, f"无法读取 {path}"
    return image


@pytest.fixture(scope="module")
def static_game_data() -> StaticGameData:
    data_root = get_root_dir() / "resources" / "data" / "v2"
    if not data_root.exists():
        pytest.skip(f"缺少静态数据 {data_root}")
    return StaticGameData(data_root)


@pytest.fixture(scope="module")
def attribute_recognizer(static_game_data: StaticGameData) -> TemplateRecognizer[str]:
    recognizer = TemplateRecognizer(
        "AttributeRecognizer", build_attribute_profile(static_game_data)
    )
    recognizer.load_templates()
    assert recognizer._templates, "属性模板未加载"
    return recognizer


@pytest.mark.parametrize(("screenshot", "stat_index"), sorted(EXPECTED))
def test_recognizes_stat_text(
    attribute_recognizer, static_game_data, screenshot, stat_index
):
    image = _load(screenshot)
    roi = [
        PROFILE.STATS_0_ROI,
        PROFILE.STATS_1_ROI,
        PROFILE.STATS_2_ROI,
    ][stat_index]
    crop = image[roi.y0 : roi.y1, roi.x0 : roi.x1]

    label, score = attribute_recognizer.recognize_roi(crop)

    expected_label, expected_name = EXPECTED[(screenshot, stat_index)]
    stat = static_game_data.get_stat(label) if label else None
    assert label == expected_label, (
        f"{screenshot} 第 {stat_index + 1} 条词条识别为 {label} "
        f"({stat.name if stat else None})，期望 {expected_name}"
    )
    assert score >= MIN_ACCEPTABLE_SCORE, (
        f"{screenshot} 第 {stat_index + 1} 条匹配分数过低: {score:.4f}"
    )


@pytest.mark.parametrize(("screenshot", "stat_index"), sorted(EXPECTED))
def test_tolerates_ui_drift(attribute_recognizer, screenshot, stat_index):
    """UI 整体上/下移若干像素后，文字仍应完整落在区域内并被正确识别。"""
    image = _load(screenshot)
    roi = [
        PROFILE.STATS_0_ROI,
        PROFILE.STATS_1_ROI,
        PROFILE.STATS_2_ROI,
    ][stat_index]
    height = roi.y1 - roi.y0
    expected_label = EXPECTED[(screenshot, stat_index)][0]

    for drift in (
        -DRIFT_TOLERANCE,
        -DRIFT_TOLERANCE // 2,
        0,
        DRIFT_TOLERANCE // 2,
        DRIFT_TOLERANCE,
    ):
        top = roi.y0 + drift
        crop = image[top : top + height, roi.x0 : roi.x1]
        label, score = attribute_recognizer.recognize_roi(crop)
        assert label == expected_label and score >= HIGH_THRESHOLD, (
            f"{screenshot} 第 {stat_index + 1} 条词条在漂移 {drift:+d}px 后识别失败: "
            f"{label} 分数={score:.4f}"
        )


def test_stats_roi_leaves_vertical_headroom():
    """区域高度必须明显大于文字高度，否则 UI 稍一移位文字就会被切掉。

    这里只卡"总余量"（高度减去文字高度），不断言单侧余量 —— 实际余量是不对称的
    （上 6px / 下 15px），真正的漂移容忍度由 `test_tolerates_ui_drift` 覆盖。
    """
    for name, roi in (
        ("STATS_0_ROI", PROFILE.STATS_0_ROI),
        ("STATS_1_ROI", PROFILE.STATS_1_ROI),
        ("STATS_2_ROI", PROFILE.STATS_2_ROI),
    ):
        height = roi.y1 - roi.y0
        headroom = height - TEXT_HEIGHT
        assert headroom >= 10, (
            f"{name} 高度 {height}px，扣除 {TEXT_HEIGHT}px 文字后只剩 {headroom}px 总余量"
        )
