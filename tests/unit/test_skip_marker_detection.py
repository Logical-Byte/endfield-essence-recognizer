"""扫描前跳过已处理过的基质：卡片状态标记检测的验证测试。

背景
----
功能：每页开始扫描前先判断哪些卡片已被用户处理过（锁定 = 保留、弃用 = 作为
养成材料），从而跳过对它们的点击与整屏识别（只省时间，判定语义不变）。
实现见 ``core/recognition/tasks/skip_marker.py`` 与 ``core/scanner/engine.py``。

本文件验证它依赖的数值前提，以及它在真实截图上的判定质量：

1. ``TestMarkerGeometry``
   标记搜索窗的几何前提：网格行列数、搜索窗必须完整覆盖角标的实际位置
   并留有余量、格距不随分辨率变化。不依赖截图，任何环境都会执行。
2. ``TestSkipMarkerDetector``
   检测器机制验证：用**合成图**精确控制"哪些格子有角标、是哪种角标"，
   断言输出集合完全正确（含误报 / 漏检 / 越界三类边界）。不依赖截图。
3. ``TestRealScreenshots``
   对两张 2560x1080 实测截图做验证：角标位置稳定性、精确率 / 召回率、
   无标记页面的零误报。截图随仓库分发，CI 中同样执行。

实测依据（2560x1080，test_a 有 57 格锁定 + 3 格弃用 / test_b 无任何标记）
---------------------------------------------------------------------
- **两种角标位置相同**：都渲染在卡片左下角，锁定角标的偏移为
  dx∈[-70, -67]、dy∈[46, 47]（跨度 3px x 1px），弃用角标为 dx=-68、dy=47。
  因此两者共用同一个 43x41 搜索窗，四边各留约 10px 余量。
- **两个模板互不干扰**（交叉分数远低于阈值）：
  锁定模板在弃用格上只有 0.338~0.342，弃用模板在锁定格上最高 0.395。
- **精确率 1.000、召回率 1.000**：锁定标记的信号为 0.819~1.000、
  弃用标记为 0.902~0.935，而无标记格最高 0.357（test_b）/ 0.350（test_a），
  空档都在 0.45 以上；阈值从 0.45 扫到 0.70 结果不变。

运行::

    uv run pytest tests/unit/test_skip_marker_detection.py -q -s
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import Point
from endfield_essence_recognizer.core.layout.dynamic import DynamicResolutionProfile
from endfield_essence_recognizer.core.recognition.tasks import (
    skip_marker as skip_marker_module,
)
from endfield_essence_recognizer.core.recognition.tasks.skip_marker import (
    _HIGH_THRESHOLD,
    _SEARCH_HEIGHT,
    _SEARCH_OFFSET_X,
    _SEARCH_OFFSET_Y,
    _SEARCH_WIDTH,
    _UNDETERMINED_SCORE,
    SkipMarkerDetector,
    SkipMarkerLabel,
)
from endfield_essence_recognizer.core.window.scaling import compute_logical_size

# ---------------------------------------------------------------------------
# 截图、模板与真值
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures"
# 两张 2560x1080 实测截图裁剪后的 WebP 夹具（quality=100，有损）。
#
# 裁剪：只保留**第 4-5 行**的搜索窗区域，横向仍是完整的 13 列，四边各留 20px 余量。
# 于是 2560x1080 -> 1948x236，配合有损压缩把两个文件从 4.6MB 压到 0.28MB。
#
# 为什么是这两行：
#   - 列漂移只由列号决定（实测第 1/2/5 行的逐列 dx 完全相同），因此测漂移
#     不需要多行 —— 第 5 行就提供了完整的 13 列（dx 跨度 3px）；
#   - 但"已弃用"样本只存在于第 4 行（4/2~4/4），所以第 4 行必须保留；
#   - 两者相邻，可以裁成一个矩形。
# 被裁掉的行不会参与判定，真值也因此只覆盖第 4-5 行（见 GROUND_TRUTH_ROWS）。
#
# 裁剪范围由 ``_SEARCH_*`` 常量推得，``TestMarkerGeometry`` 里有专门的用例
# 保证它仍然覆盖被测行的每一个搜索窗 —— 改搜索窗参数时那个用例会先报错。
#
# 注意：不要再对这两个文件做二次压缩或重新裁剪（在线工具 / cwebp 默认都是有损
# 且参数不同），那会让分数偏离当前基线。若将来断言失败，先怀疑编码差异，
# 再怀疑识别逻辑。
CROP_LEFT = 33
CROP_TOP = 683
CROP_RIGHT = 1981
CROP_BOTTOM = 919
TEST_A = _FIXTURES_DIR / "test_a.webp"
TEST_B = _FIXTURES_DIR / "test_b.webp"

# test_c：另一张实测截图，3 列 x 2 行的小网格，用于覆盖 test_a/test_b 没有的组合 ——
#   - 两张卡片底色不同（行1 无瑕基质 / 行2 高纯基质），验证稀有度不影响灰度匹配；
#   - 同一页里同时存在"无标记 / 已弃用 / 已锁定"三种状态。
# 它是按原始像素裁剪的（未缩放，角标仍是 20x20），尺寸 458x303。
# 第 1 列卡片的左边缘正好贴着图的最左边，搜索窗会向左越界，因此用例里四边补
# TEST_C_PAD 像素空白后在补边画布上判定（坐标相应平移）。
TEST_C = _FIXTURES_DIR / "test_c.webp"
TEST_C_PAD = 20
# 网格：列间距 156、行间距 155（实测，与主网格一致）
TEST_C_ICON_X = [70 + TEST_C_PAD, 226 + TEST_C_PAD, 382 + TEST_C_PAD]
TEST_C_ICON_Y = [73 + TEST_C_PAD, 228 + TEST_C_PAD]
# 维护者标注：两行均为「列1 无标记、列2 已弃用、列3 已锁定」
TEST_C_EXPECTED = {
    (0, 1): SkipMarkerLabel.DEPRECATED,
    (0, 2): SkipMarkerLabel.LOCKED,
    (1, 1): SkipMarkerLabel.DEPRECATED,
    (1, 2): SkipMarkerLabel.LOCKED,
}
TEST_C_SIZE = (458, 303)

SCREENSHOT_SIZE = (2560, 1080)

# 维护者提供的真值（来自对 test_a.png 的人工标注，行列均 1 起算）。
# 夹具只保留第 4-5 行，因此真值也只覆盖这两行（被裁掉的行无法判定）：
#   行4：列1 无标记、列2~4 已弃用、列5~13 已锁定；
#   行5：列1~13 全部已锁定。
# 合计 22 格已锁定 + 3 格已弃用 = 25 格应被跳过，1 格（4/1）从未处理过。
GROUND_TRUTH_ROWS = (4, 5)
GROUND_TRUTH_LOCKED = sorted(
    [(4, col) for col in range(5, 14)] + [(5, col) for col in range(1, 14)]
)
# 行4 的列2-4 是"弃用"标记
GROUND_TRUTH_DEPRECATED = [(4, 2), (4, 3), (4, 4)]
# 两者都属于"用户已处理过"，都应被跳过
GROUND_TRUTH_MARKED = sorted(set(GROUND_TRUTH_LOCKED) | set(GROUND_TRUTH_DEPRECATED))
# 被测范围内从未处理过的格子（这些是唯一允许被点击的格子）
GROUND_TRUTH_CLEAN = sorted(
    {(row, col) for row in GROUND_TRUTH_ROWS for col in range(1, 14)}
    - set(GROUND_TRUTH_MARKED)
)

# 网格实测结构（用于交叉校验 profile 算出的格子坐标）
MEASURED_X0 = 64
MEASURED_Y0 = 131
MEASURED_PITCH = 155.5
MEASURED_CARD_SIZE = 143

_TEMPLATE_DIR = Path("src/endfield_essence_recognizer/templates/screenshot")
LOCK_TEMPLATE = _TEMPLATE_DIR / "卡片锁定标记.png"
DELETE_TEMPLATE = _TEMPLATE_DIR / "卡片弃用标记.png"


def _profile_for(physical_width: int, physical_height: int) -> DynamicResolutionProfile:
    """按生产路径（ScalingImageSource + build_resolution_profile）构造布局配置。"""
    logical_width, logical_height, _ = compute_logical_size(
        physical_width, physical_height
    )
    return DynamicResolutionProfile(logical_width, logical_height)


def _production_template_path(relative: Path) -> Path:
    """生产模板在源码树中的位置（与 ``load_templates`` 加载的是同一个文件）。"""
    return _REPO_ROOT / relative


def _load_gray(path: Path) -> np.ndarray:
    """读入图像并转灰度。非 ASCII 路径需先读字节再 imdecode。"""
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法解码图像: {path}")
    return cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)


@pytest.fixture(scope="module")
def detector() -> SkipMarkerDetector:
    """生产检测器（与运行时同一个加载路径）。"""
    instance = SkipMarkerDetector()
    instance.load_templates()
    if not instance.loaded:
        raise AssertionError("卡片状态标记模板加载失败，生产资源可能缺失")
    return instance


# ---------------------------------------------------------------------------
# 1. 几何前提
# ---------------------------------------------------------------------------


class TestMarkerGeometry:
    """验证搜索窗几何能覆盖角标的实际位置。"""

    def test_grid_size_matches_measured_grid(self) -> None:
        """2560x1080 下应为 13 列 x 5 行（65 格），与截图实测一致。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        assert len(profile.essence_icon_x_list) == 13
        assert len(profile.essence_icon_y_list) == 5

    def test_crop_covers_every_search_window(self) -> None:
        """裁剪夹具必须覆盖被测行的每一个搜索窗。

        仓库里的截图是裁剪过的（只保留第 4-5 行以省体积）。一旦搜索窗参数被
        调整到裁剪区之外，``score_cell`` 会静默返回"无法判断"，真机用例的数字
        就会莫名其妙地变 —— 这个用例让那种情况直接报错。
        """
        profile = _profile_for(*SCREENSHOT_SIZE)
        for row in (row - 1 for row in GROUND_TRUTH_ROWS):
            icon_y = profile.essence_icon_y_list[row]
            for col, icon_x in enumerate(profile.essence_icon_x_list):
                x0 = icon_x + _SEARCH_OFFSET_X
                y0 = icon_y + _SEARCH_OFFSET_Y
                assert CROP_LEFT <= x0 and x0 + _SEARCH_WIDTH <= CROP_RIGHT, (
                    f"第 {row + 1} 行第 {col + 1} 列的搜索窗横向越出裁剪区 "
                    f"[{CROP_LEFT}, {CROP_RIGHT})"
                )
                assert CROP_TOP <= y0 and y0 + _SEARCH_HEIGHT <= CROP_BOTTOM, (
                    f"第 {row + 1} 行第 {col + 1} 列的搜索窗纵向越出裁剪区 "
                    f"[{CROP_TOP}, {CROP_BOTTOM})"
                )

    def test_search_window_covers_marker_without_reaching_neighbours(self) -> None:
        """搜索窗要完整覆盖角标的实测位置，同时够不到相邻格子的角标。

        角标（20x20）左上角相对点击坐标的偏移实测为 dx∈[-70, -67]、dy∈[46, 47]，
        即占据 x∈[-70, -47]、y∈[46, 67]。窗口在四边都要留余量以容纳不同分辨率下
        的漂移，但到相邻格角标的距离必须远大于这个余量，否则会串格误报。

        注：窗口下边界（+77）比卡片底边（约 +71）低约 6px，会覆盖到卡片之间的
        暗色间隙。该间隙远暗于角标（角标最暗 169），实测不会造成误命中。
        """
        marker_size = 20
        marker_left = -70  # 实测最小值
        marker_top = 46
        marker_right = -67 + marker_size  # 实测最大值 + 尺寸
        marker_bottom = 47 + marker_size

        window_left = _SEARCH_OFFSET_X
        window_top = _SEARCH_OFFSET_Y
        window_right = _SEARCH_OFFSET_X + _SEARCH_WIDTH
        window_bottom = _SEARCH_OFFSET_Y + _SEARCH_HEIGHT

        # 完整覆盖，四边都留有余量
        assert window_left < marker_left
        assert window_top < marker_top
        assert window_right > marker_right
        assert window_bottom > marker_bottom

        margin = min(
            marker_left - window_left,
            marker_top - window_top,
            window_right - marker_right,
            window_bottom - marker_bottom,
        )
        assert margin >= 5, f"搜索窗余量仅 {margin}px，无法容纳不同分辨率的漂移"

        # 相邻格子的角标与本格搜索窗之间必须保持隔离
        pitch = round(MEASURED_PITCH)
        assert marker_left + pitch > window_right, "搜索窗覆盖到右邻格的角标区域"
        assert marker_bottom + pitch > window_bottom, "搜索窗覆盖到下邻格的角标区域"
        assert marker_bottom - pitch < window_top, "搜索窗覆盖到上邻格的角标区域"

    def test_computed_centers_match_measured_cards(self) -> None:
        """profile 格子中心与实测卡片中心存在**固定**偏差，而非逐格累积错位。

        实测（2560x1080）：卡片外框左上角 x = 64 + 155.5i、y = 131 + 155.5j，
        边长 143。偏差稳定意味着"点击坐标 + 固定偏移"足以定位卡片内的角标，
        不需要每格单独标定。
        """
        profile = _profile_for(*SCREENSHOT_SIZE)
        columns = list(profile.essence_icon_x_list)
        rows = list(profile.essence_icon_y_list)

        measured_x = [
            MEASURED_X0 + i * MEASURED_PITCH + MEASURED_CARD_SIZE / 2
            for i in range(len(columns))
        ]
        measured_y = [
            MEASURED_Y0 + j * MEASURED_PITCH + MEASURED_CARD_SIZE / 2
            for j in range(len(rows))
        ]

        dx = [
            measured - computed
            for computed, measured in zip(columns, measured_x, strict=True)
        ]
        dy = [
            measured - computed
            for computed, measured in zip(rows, measured_y, strict=True)
        ]

        assert max(dx) - min(dx) <= 2, f"列偏差不稳定: {[round(v, 1) for v in dx]}"
        assert max(dy) - min(dy) <= 2, f"行偏差不稳定: {[round(v, 1) for v in dy]}"
        assert abs(float(np.mean(dx))) <= MEASURED_CARD_SIZE * 0.15
        assert abs(float(np.mean(dy))) <= MEASURED_CARD_SIZE * 0.15

    @pytest.mark.parametrize(
        ("width", "height"),
        [(1920, 1080), (2560, 1080), (2560, 1440), (1920, 1200)],
    )
    def test_pitch_is_resolution_independent(self, width: int, height: int) -> None:
        """网格间距是固定 UI 像素量，不随分辨率变化。

        这是"角标模板可以用同一个尺寸在所有分辨率下匹配"的前提：
        截图会先被缩放到逻辑分辨率，UI 元素在逻辑坐标下尺寸一致。
        """
        profile = _profile_for(width, height)
        columns = list(profile.essence_icon_x_list)
        rows = list(profile.essence_icon_y_list)

        assert len(columns) >= 2
        assert round(columns[1] - columns[0]) == 155
        if len(rows) >= 2:
            assert round(rows[1] - rows[0]) == 155


# ---------------------------------------------------------------------------
# 2. 检测器机制（合成图）
# ---------------------------------------------------------------------------


def _synthetic_page(
    profile: DynamicResolutionProfile,
    marked: set[tuple[int, int]],
    template: np.ndarray,
    base: np.ndarray | None = None,
) -> np.ndarray:
    """构造合成截图：在指定格子的搜索窗内贴上角标。

    背景取"卡片亮 + 间隙暗"的棋盘格并叠加轻微渐变，避免整片纯色区域
    让归一化相关系数失去意义。``base`` 用于在同一张图上叠加第二种角标。
    """
    width, height = profile.RESOLUTION
    rows = len(profile.essence_icon_y_list)
    columns = len(profile.essence_icon_x_list)

    page = (
        np.full((height, width), 200, dtype=np.uint8) if base is None else base.copy()
    )
    for row in range(rows):
        for col in range(columns):
            center_x = profile.essence_icon_x_list[col]
            center_y = profile.essence_icon_y_list[row]
            card_x0 = center_x - 72
            card_y0 = center_y - 72
            card = np.full(
                (MEASURED_CARD_SIZE, MEASURED_CARD_SIZE), 235, dtype=np.uint8
            )
            # 轻微横向渐变，模拟真实截图的亮度变化
            card[:, :] = 232 + (col % 4)
            page[
                card_y0 : card_y0 + MEASURED_CARD_SIZE,
                card_x0 : card_x0 + MEASURED_CARD_SIZE,
            ] = card

            if (row, col) in marked:
                # 贴在搜索窗的左上角：这是最不利的位置（窗口余量最小）
                x0 = center_x + _SEARCH_OFFSET_X
                y0 = center_y + _SEARCH_OFFSET_Y
                page[y0 : y0 + template.shape[0], x0 : x0 + template.shape[1]] = (
                    template
                )
    return page


def _template_array(relative: Path) -> np.ndarray:
    """读取生产标记模板（供合成图使用）。"""
    template = _load_gray(_production_template_path(relative))
    assert template.shape == (20, 20), f"模板尺寸异常: {template.shape}"
    return template


def _lock_template() -> np.ndarray:
    return _template_array(LOCK_TEMPLATE)


def _delete_template() -> np.ndarray:
    return _template_array(DELETE_TEMPLATE)


class TestSkipMarkerDetector:
    """用合成图验证检测器：贴了角标的格子必须被找出，没贴的不能误报。"""

    @pytest.mark.parametrize(
        ("template_factory", "label", "expected_label"),
        [
            (_lock_template, "锁定", SkipMarkerLabel.LOCKED),
            (_delete_template, "弃用", SkipMarkerLabel.DEPRECATED),
        ],
    )
    def test_detects_exactly_the_marked_cells(
        self,
        detector: SkipMarkerDetector,
        template_factory,
        label: str,
        expected_label: SkipMarkerLabel,
    ) -> None:
        """两种角标都要能被检出、类型正确，且不得波及其他格子。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        marked = {(0, 0), (0, 12), (2, 3), (4, 9)}
        page = _synthetic_page(profile, marked, template_factory())

        detected = detector.find_marked_cells(
            page, profile.essence_icon_x_list, profile.essence_icon_y_list
        )

        assert set(detected) == marked, (
            f"{label}标记检测结果与预期不符："
            f"漏检={marked - set(detected)}，误报={set(detected) - marked}"
        )
        assert set(detected.values()) == {expected_label}, (
            f"{label}标记的类型判定错误：{detected}"
        )

    @pytest.mark.parametrize(
        "template_factory",
        [_lock_template, _delete_template],
    )
    def test_no_false_positives_on_clean_page(
        self, detector: SkipMarkerDetector, template_factory
    ) -> None:
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, set(), template_factory())

        assert (
            detector.find_marked_cells(
                page, profile.essence_icon_x_list, profile.essence_icon_y_list
            )
            == {}
        )

    def test_mixed_markers_on_one_page(self, detector: SkipMarkerDetector) -> None:
        """同一页里两种角标混排时，结果应是两者的并集。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        locked = {(0, 0), (3, 5)}
        deprecated = {(1, 2), (4, 12)}
        page = _synthetic_page(profile, locked, _lock_template())
        page = _synthetic_page(profile, deprecated, _delete_template(), base=page)

        detected = detector.find_marked_cells(
            page, profile.essence_icon_x_list, profile.essence_icon_y_list
        )

        assert set(detected) == locked | deprecated
        assert all(detected[cell] is SkipMarkerLabel.LOCKED for cell in locked)
        assert all(detected[cell] is SkipMarkerLabel.DEPRECATED for cell in deprecated)

    def test_out_of_bounds_cell_is_not_reported(
        self, detector: SkipMarkerDetector
    ) -> None:
        """搜索窗越界的格子（翻页后顶部的半张卡片）不能被判为已处理过。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, {(0, 0)}, _lock_template())
        # 裁掉下半部分，使搜索窗超出图像范围
        page = page[: profile.essence_icon_y_list[0] + 10, :]

        assert (
            detector.find_marked_cells(
                page, profile.essence_icon_x_list, profile.essence_icon_y_list
            )
            == {}
        )

    def test_window_beyond_top_left_edge_is_undetermined(
        self, detector: SkipMarkerDetector
    ) -> None:
        """搜索窗超出图像左/上边缘时必须返回"无法判断"，不能靠负索引取到末尾像素。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, set(), _lock_template())
        height, width = page.shape[:2]
        # 让 x0 / y0 均为负且绝对值大于窗口尺寸，负索引切片会落到图像右下角
        center = Point(
            -_SEARCH_OFFSET_X - _SEARCH_WIDTH - 5,
            -_SEARCH_OFFSET_Y - _SEARCH_HEIGHT - 5,
        )
        wrapped_x0 = width + center.x + _SEARCH_OFFSET_X
        wrapped_y0 = height + center.y + _SEARCH_OFFSET_Y
        page[wrapped_y0 : wrapped_y0 + 20, wrapped_x0 : wrapped_x0 + 20] = (
            _lock_template()
        )

        assert detector.score_cell_by_label(page, center) == (
            None,
            _UNDETERMINED_SCORE,
        )

    def test_marker_outside_the_search_window_is_not_detected(
        self, detector: SkipMarkerDetector
    ) -> None:
        """角标出现在窗外的其他位置时不应命中（验证窗口确实起了约束作用）。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, set(), _lock_template())
        template = _lock_template()
        # 贴到卡片中部的武器图标位置
        x0 = profile.essence_icon_x_list[1] - 10
        y0 = profile.essence_icon_y_list[1] - 10
        page[y0 : y0 + 20, x0 : x0 + 20] = template

        assert (
            detector.find_marked_cells(
                page, profile.essence_icon_x_list, profile.essence_icon_y_list
            )
            == {}
        )

    @pytest.mark.parametrize(
        ("template_factory", "label"),
        [(_lock_template, "锁定"), (_delete_template, "弃用")],
    )
    def test_scores_separate_marked_from_unmarked(
        self, detector: SkipMarkerDetector, template_factory, label: str
    ) -> None:
        """命中与未命中的分数之间必须有明显间隔，阈值才可靠。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, {(1, 2)}, template_factory())

        scores = {
            (row, col): detector.score_cell(page, Point(x, y))
            for row, y in enumerate(profile.essence_icon_y_list)
            for col, x in enumerate(profile.essence_icon_x_list)
        }

        hit = scores[(1, 2)]
        others = [value for key, value in scores.items() if key != (1, 2)]

        assert hit >= _HIGH_THRESHOLD
        assert max(others) < _HIGH_THRESHOLD, (
            f"未标记格子的最高分 {max(others):.3f} 达到阈值，判定不可靠"
        )

    def test_unloaded_detector_reports_nothing(self) -> None:
        """模板未加载时必须安全降级：一格都不报，由调用方回退到点击后识别。"""
        profile = _profile_for(*SCREENSHOT_SIZE)
        unloaded = SkipMarkerDetector()
        assert not unloaded.loaded

        page = _synthetic_page(profile, {(0, 0)}, _lock_template())

        assert (
            unloaded.find_marked_cells(
                page, profile.essence_icon_x_list, profile.essence_icon_y_list
            )
            == {}
        )
        assert unloaded.score_cell(page, Point(100, 100)) < 0
        assert unloaded.loaded_labels == set()

    def test_partial_load_failure_keeps_working_template(self, monkeypatch) -> None:
        """只加载成功一个模板时仍可用：缺失的那个降级，不影响已加载的。"""
        failing = SkipMarkerDetector()
        original = skip_marker_module.load_image

        def flaky(path, *args, **kwargs):
            if "锁定" in str(path):
                raise ValueError("这张模板缺失")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(skip_marker_module, "load_image", flaky)
        failing.load_templates()

        assert failing.loaded, "一个模板加载成功时 loaded 应为真"
        assert failing.loaded_labels == {SkipMarkerLabel.DEPRECATED}
        profile = _profile_for(*SCREENSHOT_SIZE)
        page = _synthetic_page(profile, {(2, 4)}, _delete_template())
        assert failing.find_marked_cells(
            page, profile.essence_icon_x_list, profile.essence_icon_y_list
        ) == {(2, 4): SkipMarkerLabel.DEPRECATED}

    def test_load_failure_degrades_instead_of_raising(self, monkeypatch) -> None:
        """模板加载失败时只降级、不抛异常。

        检测器在应用启动构造 ScannerContext 时就要加载模板，
        若此处抛异常会直接阻断程序启动。
        """

        def _raise(*_args, **_kwargs):
            raise ValueError("模板缺失")

        monkeypatch.setattr(skip_marker_module, "load_image", _raise)
        failing = SkipMarkerDetector()
        failing.load_templates()

        assert not failing.loaded


# ---------------------------------------------------------------------------
# 3. 真实截图实测
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cropped_screenshots() -> tuple[np.ndarray, np.ndarray]:
    """加载裁剪后的 test_a / test_b（灰度）；缺失时跳过。"""
    missing = [path.name for path in (TEST_A, TEST_B) if not path.exists()]
    if missing:
        pytest.skip(f"缺少实测截图: {', '.join(missing)}")
    return _load_gray(TEST_A), _load_gray(TEST_B)


@pytest.fixture(scope="module")
def screenshots(
    cropped_screenshots: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """把裁剪图贴回 2560x1080 画布，使各用例可以沿用全图坐标。

    仓库里只保存裁剪后的图（省体积），这里在内存中还原成原始几何，
    于是真值、搜索窗、profile 坐标都不需要任何平移。
    """
    restored: list[np.ndarray] = []
    for cropped in cropped_screenshots:
        canvas = np.zeros((SCREENSHOT_SIZE[1], SCREENSHOT_SIZE[0]), dtype=np.uint8)
        canvas[CROP_TOP:CROP_BOTTOM, CROP_LEFT:CROP_RIGHT] = cropped
        restored.append(canvas)
    return restored[0], restored[1]


def estimate_vertical_offset(gray_a: np.ndarray, gray_b: np.ndarray) -> int:
    """估计 B 相对 A 的竖直滚动偏移（B 相对 A 整体上移为负）。

    做法：在候选整数偏移上比较重叠区域的 MAE，取最小值。
    不要用 ``cv2.matchTemplate``：卡片中部是大面积同色图标，
    ``TM_SQDIFF_NORMED`` 会被平坦区域带偏（实测给出 -2px，真实值是 -12px）。
    比较范围限定在裁剪区内，避免读到还原画布上的空白。
    """
    top, bottom = CROP_TOP + 20, CROP_BOTTOM - 20
    left, right = CROP_LEFT + 20, CROP_RIGHT - 20

    best_offset = 0
    best_score = float("inf")
    for offset in range(-40, 41):
        region_a = gray_a[top:bottom, left:right]
        region_b = gray_b[top + offset : bottom + offset, left:right]
        if region_a.shape != region_b.shape or region_a.size == 0:
            continue
        score = float(np.abs(region_a - region_b).mean())
        if score < best_score:
            best_score = score
            best_offset = offset
    return best_offset


class TestRealScreenshots:
    """对两张实测截图做验证。

    截图随仓库分发（``tests/fixtures/test_*.webp``），因此 CI 里也会执行 ——
    这是唯一能发现"游戏 UI 改了角标样式/位置"的一层保护。
    """

    def test_cropped_screenshots_have_expected_shape(
        self, cropped_screenshots: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """仓库里保存的是裁剪图，形状必须与 CROP_* 常量一致。"""
        cropped_a, cropped_b = cropped_screenshots
        assert cropped_a.shape == cropped_b.shape
        assert cropped_a.shape == (
            CROP_BOTTOM - CROP_TOP,
            CROP_RIGHT - CROP_LEFT,
        ), f"裁剪图形状与 CROP_* 常量不符: {cropped_a.shape}"

    def test_restored_canvas_matches_full_resolution(
        self, screenshots: tuple[np.ndarray, np.ndarray]
    ) -> None:
        gray_a, gray_b = screenshots
        assert gray_a.shape == gray_b.shape
        assert (gray_a.shape[1], gray_a.shape[0]) == SCREENSHOT_SIZE

    def test_cards_are_alignable_between_images(
        self, screenshots: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """两张图是同一批基质；偏移过大说明前提不成立。"""
        gray_a, gray_b = screenshots
        offset = estimate_vertical_offset(gray_a, gray_b)
        assert abs(offset) <= 40, (
            f"B 相对 A 的竖直偏移 {offset}px 过大，两张图可能不是同一批基质"
        )

    def test_marker_position_is_stable_across_cells(
        self, screenshots: tuple[np.ndarray, np.ndarray]
    ) -> None:
        """角标在每格搜索窗内的落点必须稳定，且不贴边。

        这是整个预判方案成立的**核心几何前提**：只有角标相对点击坐标的位置
        在每个格子上都一致，"点击坐标 + 固定偏移 + 模板匹配"才成立。

        实测：偏移为 dx∈[-70, -67]、dy∈[46, 47]，即跨度 3px x 1px。
        若跨度变大，说明卡片网格模型失效，搜索窗参数需要重算。

        样本来自夹具保留的第 4-5 行（22 个锁定格）：第 5 行提供完整的 13 列，
        足以覆盖列漂移；被裁掉的行搜索窗落在画布空白处，会被阈值自动滤除。
        """
        gray_a, _ = screenshots
        profile = _profile_for(*SCREENSHOT_SIZE)
        template = _lock_template()

        offsets: list[tuple[int, int]] = []
        for _row, icon_y in enumerate(profile.essence_icon_y_list):
            for _col, icon_x in enumerate(profile.essence_icon_x_list):
                x0 = icon_x + _SEARCH_OFFSET_X
                y0 = icon_y + _SEARCH_OFFSET_Y
                patch = gray_a[y0 : y0 + _SEARCH_HEIGHT, x0 : x0 + _SEARCH_WIDTH]
                if patch.shape[0] < template.shape[0]:
                    continue
                result = cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)
                _, best, _, loc = cv2.minMaxLoc(result)
                if best < _HIGH_THRESHOLD:
                    continue
                # 角标左上角相对点击坐标的偏移
                offsets.append((loc[0] + _SEARCH_OFFSET_X, loc[1] + _SEARCH_OFFSET_Y))

        assert len(offsets) >= 20, f"可用样本太少（{len(offsets)}），无法评估位置稳定性"

        xs = np.array([x for x, _ in offsets])
        ys = np.array([y for _, y in offsets])
        print(
            f"\n[角标位置稳定性] 样本 {len(offsets)} 格："
            f"x∈[{xs.min()},{xs.max()}] (跨度 {xs.max() - xs.min()}px)，"
            f"y∈[{ys.min()},{ys.max()}] (跨度 {ys.max() - ys.min()}px)"
        )

        assert xs.max() - xs.min() <= 8, (
            f"横向位置跨度 {xs.max() - xs.min()}px 过大，卡片网格模型可能已失效"
        )
        assert ys.max() - ys.min() <= 8, (
            f"纵向位置跨度 {ys.max() - ys.min()}px 过大，卡片网格模型可能已失效"
        )

    def test_detect_marked_cells_matches_ground_truth(
        self, screenshots: tuple[np.ndarray, np.ndarray], detector: SkipMarkerDetector
    ) -> None:
        """在 test_a 上判定被标记的格子，并与维护者标注的真值对比。

        真值 = 57 个已锁定 + 3 个已弃用，共 60 格。
        """
        gray_a, _ = screenshots
        profile = _profile_for(*SCREENSHOT_SIZE)

        marked_cells = {
            (row + 1, col + 1): label
            for (row, col), label in detector.find_marked_cells(
                gray_a, profile.essence_icon_x_list, profile.essence_icon_y_list
            ).items()
        }
        detected = set(marked_cells)
        truth = set(GROUND_TRUTH_MARKED)

        true_positive = detected & truth
        false_positive = detected - truth
        false_negative = truth - detected
        precision = len(true_positive) / len(detected) if detected else 0.0
        recall = len(true_positive) / len(truth) if truth else 0.0

        # 分类必须正确：锁定格报 LOCKED、弃用格报 DEPRECATED。
        # 这是"日志能把两类分开显示"和"两个开关能各自生效"的前提。
        label_errors = {
            cell: marked_cells[cell]
            for cell in true_positive
            if marked_cells[cell]
            is not (
                SkipMarkerLabel.DEPRECATED
                if cell in set(GROUND_TRUTH_DEPRECATED)
                else SkipMarkerLabel.LOCKED
            )
        }
        assert not label_errors, f"标记类型判定错误: {label_errors}"

        print(
            f"\n[标记判定] n={len(detected)} 精确率={precision:.3f} 召回率={recall:.3f}\n"
            f"  误报 {sorted(false_positive)}\n  漏检 {sorted(false_negative)}"
        )

        # 误报会导致"本该处理的基质被跳过"，是危害最大的方向，必须严格为零。
        # 这也正是本功能可以只做"省时间"优化、不改变任何判定语义的前提。
        assert not false_positive, f"出现误报（会漏处理基质）: {sorted(false_positive)}"

        # 召回率要求 100%：漏检只会退化成"点击后识别"（不省时间但不会错判），
        # 不过实测在本样本上可以做到零漏检，因此按 100% 卡住，
        # 一旦将来出现漏检就说明几何/模板/阈值需要重新标定。
        assert not false_negative, f"出现漏检（{recall:.3f}）: {sorted(false_negative)}"

    def test_both_marker_types_are_individually_detected(
        self, screenshots: tuple[np.ndarray, np.ndarray], detector: SkipMarkerDetector
    ) -> None:
        """两类标记都要真的被识别出来，而不是靠其中一类凑数。

        用"逐个模板单独匹配"复算一遍：只放锁定模板时必须且只能找出 57 格，
        只放弃用模板时必须且只能找出 4/2~4/4 这 3 格。
        """
        gray_a, _ = screenshots
        profile = _profile_for(*SCREENSHOT_SIZE)

        single_scores: dict[str, dict[tuple[int, int], float]] = {}
        for label, template in (
            ("锁定", _lock_template()),
            ("弃用", _delete_template()),
        ):
            # 复用生产搜索窗几何，但只用单个模板
            scores = {
                (row + 1, col + 1): float(
                    cv2.matchTemplate(
                        gray_a[
                            icon_y + _SEARCH_OFFSET_Y : icon_y
                            + _SEARCH_OFFSET_Y
                            + _SEARCH_HEIGHT,
                            icon_x + _SEARCH_OFFSET_X : icon_x
                            + _SEARCH_OFFSET_X
                            + _SEARCH_WIDTH,
                        ],
                        template,
                        cv2.TM_CCOEFF_NORMED,
                    ).max()
                )
                for row, icon_y in enumerate(profile.essence_icon_y_list)
                for col, icon_x in enumerate(profile.essence_icon_x_list)
            }
            single_scores[label] = scores

        locked_hits = {
            c for c, v in single_scores["锁定"].items() if v >= _HIGH_THRESHOLD
        }
        deprecated_hits = {
            c for c, v in single_scores["弃用"].items() if v >= _HIGH_THRESHOLD
        }
        print(
            f"\n[单模板复算] 锁定模板命中 {len(locked_hits)} 格，"
            f"弃用模板命中 {len(deprecated_hits)} 格"
            f"（弃用格噪声最高 "
            f"{max(v for c, v in single_scores['弃用'].items() if c in set(GROUND_TRUTH_LOCKED)):.3f}）"
        )

        assert locked_hits == set(GROUND_TRUTH_LOCKED)
        assert deprecated_hits == set(GROUND_TRUTH_DEPRECATED)

        # 交叉污染检查：锁定模板不得把弃用格判为锁定，反之亦然。
        assert not (locked_hits & set(GROUND_TRUTH_DEPRECATED))
        assert not (deprecated_hits & set(GROUND_TRUTH_LOCKED))

    def test_detects_nothing_on_clean_page(
        self, screenshots: tuple[np.ndarray, np.ndarray], detector: SkipMarkerDetector
    ) -> None:
        """test_b 没有任何标记，检测器在这里必须一格都不报（零误报回归）。"""
        _, gray_b = screenshots
        profile = _profile_for(*SCREENSHOT_SIZE)

        detected = detector.find_marked_cells(
            gray_b, profile.essence_icon_x_list, profile.essence_icon_y_list
        )

        assert detected == {}, f"无标记页面上出现误报: {detected}"

    def test_score_gap_between_marked_and_clean(
        self, screenshots: tuple[np.ndarray, np.ndarray], detector: SkipMarkerDetector
    ) -> None:
        """阈值必须落在"噪声底"与"信号"之间的空档里。

        这是阈值可靠性的直接证据：空档越宽，越不依赖阈值的精确取值。
        """
        gray_a, gray_b = screenshots
        profile = _profile_for(*SCREENSHOT_SIZE)
        truth = set(GROUND_TRUTH_MARKED)

        def scores_of(gray: np.ndarray) -> dict[tuple[int, int], float]:
            return {
                (row + 1, col + 1): detector.score_cell(gray, Point(icon_x, icon_y))
                for row, icon_y in enumerate(profile.essence_icon_y_list)
                for col, icon_x in enumerate(profile.essence_icon_x_list)
            }

        scores_a = scores_of(gray_a)
        scores_b = scores_of(gray_b)

        marked_scores = [score for cell, score in scores_a.items() if cell in truth]
        clean_scores = [score for cell, score in scores_a.items() if cell not in truth]
        clean_scores += list(scores_b.values())

        lowest_marked = min(marked_scores)
        highest_clean = max(clean_scores)
        print(
            f"\n[分数间隔] 已标记最低={lowest_marked:.3f}，"
            f"未标记最高={highest_clean:.3f}，"
            f"空档={lowest_marked - highest_clean:.3f}，阈值={_HIGH_THRESHOLD:.2f}"
        )

        assert lowest_marked > _HIGH_THRESHOLD > highest_clean, (
            "阈值没有落在信号与噪声的空档里，判定不可靠"
        )
        assert lowest_marked - highest_clean >= 0.3, (
            f"空档仅 {lowest_marked - highest_clean:.3f}，阈值过于敏感"
        )


# ---------------------------------------------------------------------------
# 4. test_c：小网格 + 混合稀有度
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def compact_page() -> np.ndarray:
    """加载 test_c（灰度）并在四边补空白，使每格的搜索窗都不越界。"""
    if not TEST_C.exists():
        pytest.skip(f"缺少实测截图: {TEST_C.name}")
    image = _load_gray(TEST_C)
    height, width = image.shape
    if (width, height) != TEST_C_SIZE:
        raise AssertionError(f"test_c 尺寸变化: {(width, height)} != {TEST_C_SIZE}")
    canvas = np.zeros((height + 2 * TEST_C_PAD, width + 2 * TEST_C_PAD), dtype=np.uint8)
    canvas[TEST_C_PAD : TEST_C_PAD + height, TEST_C_PAD : TEST_C_PAD + width] = image
    return canvas


class TestCompactGridScreenshot:
    """test_c：3 列 x 2 行的小网格，同时覆盖两种稀有度与三种状态。

    test_a/test_b 是同一副网格的两种标记状态，卡片稀有度构成也一致；
    test_c 补上了两块空白：

    1. **稀有度**：行1 是无瑕基质、行2 是高纯基质，卡片底色不同
       （实测灰度底色差异让标记分数掉 0.026~0.038，判定不受影响）；
    2. **小网格**：只有 3x2，验证检测器只依赖传入的格子坐标、
       不隐含任何关于网格规模的假设。
    """

    def test_detects_marked_cells_with_mixed_rarity(
        self, detector: SkipMarkerDetector, compact_page: np.ndarray
    ) -> None:
        """两行的标记都要被正确识别，且类型正确。"""
        detected = detector.find_marked_cells(
            compact_page, TEST_C_ICON_X, TEST_C_ICON_Y
        )

        print(f"\n[test_c 判定] {detected}")
        assert detected == TEST_C_EXPECTED, (
            f"与维护者标注不符：漏检={set(TEST_C_EXPECTED) - set(detected)}，"
            f"误报={set(detected) - set(TEST_C_EXPECTED)}"
        )

    def test_both_rarities_clear_the_threshold(
        self, detector: SkipMarkerDetector, compact_page: np.ndarray
    ) -> None:
        """两种稀有度的标记分数都要远离阈值，未标记格要明显低于阈值。"""
        scores: dict[tuple[int, int], float] = {}
        for row, icon_y in enumerate(TEST_C_ICON_Y):
            for col, icon_x in enumerate(TEST_C_ICON_X):
                scores[(row, col)] = detector.score_cell(
                    compact_page, Point(icon_x, icon_y)
                )

        marked = [scores[cell] for cell in TEST_C_EXPECTED]
        clean = [score for cell, score in scores.items() if cell not in TEST_C_EXPECTED]

        # 逐行对比：验证稀有度带来的偏移量级很小
        for col in (1, 2):
            print(
                f"  列{col + 1}: 无瑕={scores[(0, col)]:.3f} "
                f"高纯={scores[(1, col)]:.3f} 差={abs(scores[(0, col)] - scores[(1, col)]):.3f}"
            )
        print(
            f"[test_c 分数] 已标记最低={min(marked):.3f}，"
            f"未标记最高={max(clean):.3f}，空档={min(marked) - max(clean):.3f}"
        )

        assert min(marked) > _HIGH_THRESHOLD > max(clean)
        assert min(marked) - max(clean) >= 0.3

    def test_padding_keeps_every_search_window_inside(
        self, compact_page: np.ndarray
    ) -> None:
        """补边必须足够，否则越界格会静默返回"无法判断"。"""
        height, width = compact_page.shape
        for row, icon_y in enumerate(TEST_C_ICON_Y):
            for col, icon_x in enumerate(TEST_C_ICON_X):
                x0 = icon_x + _SEARCH_OFFSET_X
                y0 = icon_y + _SEARCH_OFFSET_Y
                assert x0 >= 0 and x0 + _SEARCH_WIDTH <= width, (
                    f"第 {row + 1} 行第 {col + 1} 列横向越界（补边不足）"
                )
                assert y0 >= 0 and y0 + _SEARCH_HEIGHT <= height, (
                    f"第 {row + 1} 行第 {col + 1} 列纵向越界（补边不足）"
                )
