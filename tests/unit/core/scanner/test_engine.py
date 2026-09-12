import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import (
    Point,
    Region,
    ResolutionProfile,
)
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    AttributeLevelRecognizer,
    LockStatusLabel,
    RarityLabel,
    SkipMarkerDetector,
    SkipMarkerLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.recognition.template_recognizer import (
    TemplateRecognizer,
)
from endfield_essence_recognizer.core.scanner import engine as scanner_engine_module
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.scanner.engine import (
    DraggableScannerEngine,
    ScannerEngine,
)
from endfield_essence_recognizer.schemas.user_setting import (
    EssenceStats,
    UserSetting,
)
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


class MockImageSource:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height

    def get_client_size(self) -> tuple[int, int]:
        return self.width, self.height

    def screenshot(self, relative_region: Region | None = None) -> np.ndarray:
        # Return a dummy black image
        if relative_region is not None:
            w = relative_region.x1 - relative_region.x0
            h = relative_region.y1 - relative_region.y0
        else:
            w, h = self.width, self.height
        return np.zeros((h, w, 3), dtype=np.uint8)


class MockWindowActions:
    def __init__(self):
        self._target_exists = True
        self._target_is_active = True
        self.click_calls = []

    @property
    def target_exists(self) -> bool:
        return self._target_exists

    @property
    def target_is_active(self) -> bool:
        return self._target_is_active

    def restore(self) -> bool:
        return True

    def activate(self) -> bool:
        return True

    def show(self) -> bool:
        return True

    def click(self, relative_x: int, relative_y: int) -> None:
        self.click_calls.append((relative_x, relative_y))

    def wait(self, seconds: float) -> None:
        pass


@pytest.fixture
def mock_scanner_context():
    # Mock recognizers
    ui_scene_recognizer = MagicMock(spec=TemplateRecognizer)
    ui_scene_recognizer.recognize_roi_fallback.return_value = (
        UISceneLabel.ESSENCE_UI,
        1.0,
    )

    attr_recognizer = MagicMock(spec=TemplateRecognizer)
    attr_recognizer.recognize_roi.return_value = ("atk", 0.9)  # Dummy attribute

    attr_level_recognizer = MagicMock(spec=AttributeLevelRecognizer)
    attr_level_recognizer.recognize_level.return_value = 10

    abandon_status_recognizer = MagicMock(spec=TemplateRecognizer)
    abandon_status_recognizer.recognize_roi_fallback.return_value = (
        AbandonStatusLabel.NOT_ABANDONED,
        0.9,
    )

    lock_status_recognizer = MagicMock(spec=TemplateRecognizer)
    lock_status_recognizer.recognize_roi_fallback.return_value = (
        LockStatusLabel.NOT_LOCKED,
        0.9,
    )

    rarity_recognizer = MagicMock(spec=TemplateRecognizer)
    rarity_recognizer.recognize_roi_fallback.return_value = (
        RarityLabel.OTHER,
        0.9,
    )

    skip_marker_detector = MagicMock(spec=SkipMarkerDetector)
    skip_marker_detector.loaded = True
    skip_marker_detector.loaded_labels = {
        SkipMarkerLabel.LOCKED,
        SkipMarkerLabel.DEPRECATED,
    }
    skip_marker_detector.find_marked_cells.return_value = {}

    static_game_data = MagicMock()
    # Mock return value for get_stat to avoid errors when formatting logs
    static_game_data.get_stat.return_value = MagicMock(name="TestStat")
    # Mock list_weapons to return empty list (no real weapon data needed for engine tests)
    static_game_data.list_weapons.return_value = []
    # Mock get_weapon to return None (no weapon found)
    static_game_data.get_weapon.return_value = None

    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        skip_marker_detector=skip_marker_detector,
        rarity_recognizer=rarity_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
        static_game_data=static_game_data,
    )


@pytest.fixture
def mock_user_setting_manager():
    manager = MagicMock(spec=UserSettingManager)
    manager.get_user_setting.return_value = UserSetting()
    return manager


@pytest.fixture
def mock_profile():
    profile = MagicMock(spec=ResolutionProfile)
    profile.RESOLUTION = (1920, 1080)
    # Use real Region/Point so InMemoryImageSource.screenshot(roi) crops correctly
    profile.ESSENCE_UI_ROI = Region(Point(38, 66), Point(143, 106))
    profile.STATS_0_ROI = Region(Point(1508, 358), Point(1700, 390))
    profile.STATS_1_ROI = Region(Point(1508, 416), Point(1700, 448))
    profile.STATS_2_ROI = Region(Point(1508, 468), Point(1700, 500))
    profile.DEPRECATE_BUTTON_ROI = Region(Point(1790, 270), Point(1823, 302))
    profile.LOCK_BUTTON_ROI = Region(Point(1825, 270), Point(1857, 302))
    profile.LOCK_BUTTON_POS = Point(1839, 286)
    profile.DEPRECATE_BUTTON_POS = Point(1807, 284)

    # Mock just one essence icon for simplicity
    profile.essence_icon_x_list = [100]
    profile.essence_icon_y_list = [200]
    return profile


@pytest.mark.skip_in_ci(reason="Skip scanner engine tests in CI environment")
def test_scanner_engine_execution(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    image_source = MockImageSource()
    window_actions = MockWindowActions()

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    stop_event = threading.Event()

    # Run execute
    engine.execute(stop_event)

    # Check if click was called
    assert len(window_actions.click_calls) >= 1
    assert window_actions.click_calls[0] == (100, 200)

    # Check if recognition happened
    mock_scanner_context.attr_recognizer.recognize_roi.assert_called()


def test_scanner_engine_stop_event(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    image_source = MockImageSource()
    window_actions = MockWindowActions()

    # Increase grid to ensure we can catch it stopping
    mock_profile.essence_icon_x_list = [100, 200]
    mock_profile.essence_icon_y_list = [200]

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    stop_event = threading.Event()
    stop_event.set()  # Set stop immediately

    engine.execute(stop_event)

    # If stopped immediately, it should loop but see stop_event.is_set() and break before clicking
    assert len(window_actions.click_calls) == 0


def test_recognize_essence_screenshot_calls(mock_scanner_context, mock_profile):
    from endfield_essence_recognizer.core.scanner.engine import recognize_essence

    image_source = MagicMock()
    # Mock screenshot to return a dummy image based on the profile resolution
    image_source.screenshot.return_value = np.zeros(
        (mock_profile.RESOLUTION[1], mock_profile.RESOLUTION[0], 3), dtype=np.uint8
    )
    image_source.get_client_size.return_value = mock_profile.RESOLUTION

    recognize_essence(image_source, mock_scanner_context, mock_profile)

    # It should only be called ONCE inside recognize_essence (by cache_from)
    assert image_source.screenshot.call_count == 1


def test_recognize_once_screenshot_calls(mock_scanner_context, mock_profile):
    from endfield_essence_recognizer.core.scanner.engine import recognize_once

    image_source = MagicMock()
    image_source.screenshot.return_value = np.zeros(
        (mock_profile.RESOLUTION[1], mock_profile.RESOLUTION[0], 3), dtype=np.uint8
    )
    image_source.get_client_size.return_value = mock_profile.RESOLUTION

    recognize_once(image_source, mock_scanner_context, UserSetting(), mock_profile)

    # It should only be called ONCE inside recognize_once
    assert image_source.screenshot.call_count == 1


def test_scanner_engine_screenshot_count(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    image_source = MagicMock()
    image_source.screenshot.return_value = np.zeros(
        (mock_profile.RESOLUTION[1], mock_profile.RESOLUTION[0], 3), dtype=np.uint8
    )
    image_source.get_client_size.return_value = mock_profile.RESOLUTION

    window_actions = MockWindowActions()

    # Only 1 icon to scan
    mock_profile.essence_icon_x_list = [100]
    mock_profile.essence_icon_y_list = [200]

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    stop_event = threading.Event()
    engine.execute(stop_event)

    # 1 call for check_scene + 1 call for recognize_essence
    assert image_source.screenshot.call_count == 2


@pytest.mark.parametrize(
    ("enabled", "expected_calls"),
    [
        (True, 1),
        (False, 0),
    ],
)
def test_draggable_scanner_row_alignment_setting(
    mock_scanner_context,
    mock_user_setting_manager,
    mock_profile,
    monkeypatch,
    enabled,
    expected_calls,
):
    setting = UserSetting(auto_page_flip=True)
    setting.fix_grid_row_offset_after_page_flip = enabled
    mock_user_setting_manager.get_user_setting.return_value = setting

    mock_profile.essence_icon_x_list = [100]
    mock_profile.essence_icon_y_list = [200, 300]
    mock_profile.DRAG_START_POS = Point(100, 900)
    mock_profile.DRAG_END_POS = Point(100, 100)
    mock_profile.SCROLLBAR_CHECK_POS = None

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    align_mock = MagicMock()
    monkeypatch.setattr(scanner_engine_module, "check_scene", lambda *_args: True)
    monkeypatch.setattr(engine, "_scan_current_page", MagicMock())
    monkeypatch.setattr(engine, "_scan_single_row", MagicMock(return_value=False))
    monkeypatch.setattr(
        engine,
        "_progressive_drag",
        MagicMock(side_effect=[(800, False), (100, True)]),
    )
    monkeypatch.setattr(engine, "_align_grid_rows_after_drag", align_mock)
    monkeypatch.setattr(
        engine, "_check_scrollbar_at_bottom", MagicMock(return_value=False)
    )

    engine.execute(threading.Event())

    assert align_mock.call_count == expected_calls


@pytest.mark.parametrize(
    ("enabled", "expected_calls"),
    [
        (True, 1),
        (False, 0),
    ],
)
def test_draggable_scanner_overscroll_setting(
    mock_scanner_context,
    mock_user_setting_manager,
    mock_profile,
    monkeypatch,
    enabled,
    expected_calls,
):
    setting = UserSetting(auto_page_flip=True)
    setting.fix_grid_row_offset_after_page_flip = False
    setting.fix_page_flip_overscroll = enabled
    mock_user_setting_manager.get_user_setting.return_value = setting

    mock_profile.essence_icon_x_list = [100]
    mock_profile.essence_icon_y_list = [200, 300]
    mock_profile.DRAG_START_POS = Point(100, 900)
    mock_profile.DRAG_END_POS = Point(100, 100)
    mock_profile.SCROLLBAR_CHECK_POS = None

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    correct_mock = MagicMock()
    monkeypatch.setattr(scanner_engine_module, "check_scene", lambda *_args: True)
    monkeypatch.setattr(engine, "_scan_current_page", MagicMock())
    monkeypatch.setattr(engine, "_scan_single_row", MagicMock(return_value=True))
    monkeypatch.setattr(
        engine,
        "_progressive_drag",
        MagicMock(side_effect=[(800, False), (100, True)]),
    )
    monkeypatch.setattr(engine, "_correct_overscroll", correct_mock)
    monkeypatch.setattr(
        engine, "_check_scrollbar_at_bottom", MagicMock(return_value=False)
    )

    engine.execute(threading.Event())

    assert correct_mock.call_count == expected_calls


def test_exact_level_skip_isolated_by_level(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    weapon = SimpleNamespace(
        name="TestWeapon", stat1_id="attr", stat2_id="secondary", stat3_id="skill"
    )
    mock_scanner_context.static_game_data.get_weapon.return_value = weapon
    engine._sort_weapons_by_priority = lambda _ids: ["w1", "w2"]

    engine._weapon_essence_levels = {"w1": (1, 1, 1)}
    engine._assign_essence_to_weapon({"w1", "w2"}, [1, 1, 1])
    assert engine.get_weapon_essence_counts() == {}

    engine._weapon_essence_levels = {"w1": (1, 1, 1), "w2": (2, 1, 1)}
    engine._assign_essence_to_weapon({"w1", "w2"}, [2, 1, 1])

    assert engine.get_weapon_essence_counts() == {}


def test_sort_weapons_by_priority_deterministic_tie_break(
    monkeypatch,
    mock_scanner_context,
    mock_user_setting_manager,
    mock_profile,
):
    """同稀有度武器按 ID 升序排序，分配顺序确定可复现。"""
    from endfield_essence_recognizer.api.routes import profiles as profiles_routes

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    profile_manager = MagicMock()
    profile_manager.get_active_profile.return_value = SimpleNamespace(
        treasure_matrix=[], weapon_priorities={}
    )
    monkeypatch.setattr(profiles_routes, "get_profile_manager", lambda: profile_manager)

    def fake_get_weapon(weapon_id):
        if weapon_id in ("wpn_b", "wpn_a", "wpn_c", "wpn_low"):
            rarity = 5 if weapon_id == "wpn_low" else 6
            return SimpleNamespace(name=weapon_id, rarity=rarity)
        return None

    mock_scanner_context.static_game_data.get_weapon.side_effect = fake_get_weapon

    # 同稀有度：按武器 ID 升序
    assert engine._sort_weapons_by_priority({"wpn_b", "wpn_a", "wpn_c"}) == [
        "wpn_a",
        "wpn_b",
        "wpn_c",
    ]
    # 不同稀有度：稀有度降序优先
    assert engine._sort_weapons_by_priority({"wpn_low", "wpn_a"}) == [
        "wpn_a",
        "wpn_low",
    ]


def test_downgrade_blocked_essence_is_not_fallback_counted(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    weapon = SimpleNamespace(
        name="TestWeapon", stat1_id="attr", stat2_id="secondary", stat3_id="skill"
    )
    mock_scanner_context.static_game_data.get_weapon.return_value = weapon
    engine._sort_weapons_by_priority = lambda _ids: ["w1"]
    engine._weapon_essence_levels = {"w1": (3, 3, 2)}

    engine._assign_essence_to_weapon({"w1"}, [2, 3, 1])

    assert engine.get_weapon_essence_counts() == {}


def test_get_weapon_essence_counts_group_aggregation(
    monkeypatch, mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """组扫描计数存在时，组内每把武器（孪生）都显示该属性组合的组总数。"""
    from endfield_essence_recognizer.core.scanner.claimer import ClaimContext

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    # 创建 ClaimContext 并设置组扫描计数
    claim_ctx = ClaimContext([], UserSetting())
    claim_ctx.group_scanned = {("A", "B", "C"): 3}
    engine._claim_context = claim_ctx

    mock_scanner_context.static_game_data.find_weapons_by_stats.side_effect = (
        lambda attr, sec, skill: (
            ["wpn_a", "wpn_b"] if (attr, sec, skill) == ("A", "B", "C") else []
        )
    )
    engine._weapon_essence_counts = {"wpn_a": 1}

    assert engine.get_weapon_essence_counts() == {"wpn_a": 3, "wpn_b": 3}
    assert engine.get_weapon_essence_data().counts == {"wpn_a": 3, "wpn_b": 3}


def test_get_weapon_essence_counts_fallback_without_group_counts(
    monkeypatch, mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """无组扫描计数时回退为逐武器认领计数。"""
    from endfield_essence_recognizer.core.scanner.claimer import ClaimContext

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    # 创建 ClaimContext 但不设置组扫描计数（空）
    claim_ctx = ClaimContext([], UserSetting())
    engine._claim_context = claim_ctx

    engine._weapon_essence_counts = {"wpn_a": 2}

    assert engine.get_weapon_essence_counts() == {"wpn_a": 2}


def _make_screenshot_with_gaps(
    width: int,
    height: int,
    gap_y_centers: list[int],
    gap_thickness: int = 9,
    card_brightness: int = 150,
    gap_brightness: int = 20,
) -> np.ndarray:
    """生成带有指定暗带位置的模拟截图，用于间隙检测测试。"""
    img = np.full((height, width, 3), card_brightness, dtype=np.uint8)
    half = gap_thickness // 2
    for gap_center in gap_y_centers:
        top = max(0, gap_center - half)
        bottom = min(height, gap_center + half + 1)
        img[top:bottom, :, :] = gap_brightness
    return img


class GapDetectImageSource:
    """用于测试间隙检测的模拟图像源，返回预设暗带位置的截图。"""

    def __init__(self, screenshot_img: np.ndarray):
        self._img = screenshot_img

    def get_client_size(self) -> tuple[int, int]:
        return self._img.shape[1], self._img.shape[0]

    def screenshot(self, relative_region: Region | None = None) -> np.ndarray:
        if relative_region is None:
            return self._img.copy()
        return self._img[
            relative_region.y0 : relative_region.y1,
            relative_region.x0 : relative_region.x1,
            :,
        ].copy()


def test_gap_detection_returns_correct_offset(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """当截图中的暗带相对于期望位置有固定偏移时，检测应返回该偏移量。"""
    icon_y_list = [200, 355, 510, 665, 820]
    row_height = 155
    card_half = row_height // 2

    # 期望间隙中心：(200+72 + 355-72)/2 = 277, 432, 587, 742
    expected_gaps = []
    for i in range(len(icon_y_list) - 1):
        expected_gaps.append(
            (icon_y_list[i] + card_half + icon_y_list[i + 1] - card_half) // 2
        )

    # 实际暗带偏移 +10px
    offset = 10
    actual_gaps = [g + offset for g in expected_gaps]

    img = _make_screenshot_with_gaps(1920, 1049, actual_gaps)
    image_source = GapDetectImageSource(img)

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    result = engine._detect_grid_row_offset([100, 500], icon_y_list, row_height)
    assert result is not None
    # 允许 ±1px 的量化误差
    assert abs(result - offset) <= 1


def test_gap_detection_returns_none_for_no_gaps(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """截图中没有暗带时，应返回 None。"""
    img = np.full((1049, 1920, 3), 150, dtype=np.uint8)
    image_source = GapDetectImageSource(img)

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    result = engine._detect_grid_row_offset([100, 500], [200, 355, 510], 155)
    assert result is None


def test_gap_detection_handles_negative_offset(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """暗带位于期望位置上方（负偏移）时，应正确检测。"""
    icon_y_list = [200, 355, 510]
    row_height = 155
    card_half = row_height // 2

    expected_gaps = []
    for i in range(len(icon_y_list) - 1):
        expected_gaps.append(
            (icon_y_list[i] + card_half + icon_y_list[i + 1] - card_half) // 2
        )

    offset = -15
    actual_gaps = [g + offset for g in expected_gaps]

    img = _make_screenshot_with_gaps(1920, 1049, actual_gaps)
    image_source = GapDetectImageSource(img)

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    result = engine._detect_grid_row_offset([100, 500], icon_y_list, row_height)
    assert result is not None
    assert abs(result - offset) <= 1


def test_gap_detection_large_offset_with_spacing(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """偏移量超过旧容差（30px）时，通过相对间距匹配仍应正确检测。"""
    icon_y_list = [200, 355, 510, 665, 820]
    row_height = 155
    card_half = row_height // 2

    expected_gaps = []
    for i in range(len(icon_y_list) - 1):
        expected_gaps.append(
            (icon_y_list[i] + card_half + icon_y_list[i + 1] - card_half) // 2
        )

    # 大偏移 +50px，超过旧的 30px 容差
    offset = 50
    actual_gaps = [g + offset for g in expected_gaps]

    img = _make_screenshot_with_gaps(1920, 1049, actual_gaps)
    image_source = GapDetectImageSource(img)

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    result = engine._detect_grid_row_offset([100, 500], icon_y_list, row_height)
    assert result is not None
    assert abs(result - offset) <= 1


def test_gap_detection_filters_noise_by_spacing(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """噪声暗带（间距不等于 row_height）应被过滤，不影响偏移计算。"""
    icon_y_list = [200, 355, 510, 665, 820]
    row_height = 155
    card_half = row_height // 2

    expected_gaps = []
    for i in range(len(icon_y_list) - 1):
        expected_gaps.append(
            (icon_y_list[i] + card_half + icon_y_list[i + 1] - card_half) // 2
        )

    # 正确间隙偏移 +10px，但在前面加一条噪声暗带
    offset = 10
    actual_gaps = [g + offset for g in expected_gaps]
    noise_gap = actual_gaps[0] - 80  # 间距 80px，不等于 row_height
    all_gaps = [noise_gap] + actual_gaps

    img = _make_screenshot_with_gaps(1920, 1049, all_gaps)
    image_source = GapDetectImageSource(img)

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=image_source,
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    result = engine._detect_grid_row_offset([100, 500], icon_y_list, row_height)
    assert result is not None
    # 噪声暗带被过滤，偏移仍由有效暗带决定
    assert abs(result - offset) <= 1


def _make_same_type_engine(
    mock_scanner_context, mock_user_setting_manager, mock_profile, treasure_matrix
):
    """构造已注入 mock profile 数据的 ScannerEngine。"""
    from endfield_essence_recognizer.core.scanner.engine import ScannerEngine

    profile_manager = MagicMock()
    profile_manager.get_active_profile.return_value = SimpleNamespace(
        treasure_matrix=treasure_matrix
    )

    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )
    return engine, profile_manager


def test_init_same_type_levels_counts_existing_entries(
    monkeypatch, mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """初始化同类型状态：存量条数计入限额名额（总保有量语义）。"""
    from endfield_essence_recognizer.core.scanner.claimer import ClaimContext
    from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

    entries = [
        TreasureMatrixEntry(
            weapon_id="wpn_sword_0001",
            weapon_name="测试武器",
            affix1_level=3,
            affix2_level=3,
            affix3_level=3,
        ),
        TreasureMatrixEntry(
            weapon_id="wpn_sword_0001",
            weapon_name="测试武器",
            affix1_level=3,
            affix2_level=3,
            affix3_level=3,
        ),
        TreasureMatrixEntry(
            weapon_id="wpn_lance_0001",
            weapon_name="测试长枪",
            affix1_level=2,
            affix2_level=2,
            affix3_level=1,
        ),
    ]

    user_setting = UserSetting()
    ctx = ClaimContext(entries, user_setting, mock_scanner_context.static_game_data)

    # 每把武器：计数 = 存量条数，最佳等级 = 组内最高，相等跳过名额 = 等于最佳的数量
    assert ctx.treasure_counts["wpn_sword_0001"] == 2
    assert ctx.best_levels["wpn_sword_0001"] == (3, 3, 3)
    assert ctx.equal_skips["wpn_sword_0001"] == 2
    assert ctx.treasure_counts["wpn_lance_0001"] == 1
    assert ctx.best_levels["wpn_lance_0001"] == (2, 2, 1)
    assert ctx.equal_skips["wpn_lance_0001"] == 1


def test_init_same_type_levels_custom_entries_feed_stat_key_counts(
    monkeypatch, mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """自定义基质条目的存量按配置属性组合计入 stat_key 计数（BY_STAT 总保有量）。"""
    from endfield_essence_recognizer.core.scanner.claimer import ClaimContext
    from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry

    entries = [
        TreasureMatrixEntry(
            weapon_id="custom:abc",
            weapon_name="自定义X",
            affix1_level=2,
            affix2_level=1,
            affix3_level=1,
        )
    ]

    user_setting = UserSetting()
    user_setting.treasure_essence_stats = [
        EssenceStats(id="abc", name="自定义X", attribute="A", secondary="B", skill="C")
    ]
    ctx = ClaimContext(entries, user_setting, mock_scanner_context.static_game_data)

    # 自定义条目既计入自身 weapon_id，也按配置的属性组合计入 stat_key
    assert ctx.treasure_counts["custom:abc"] == 1
    assert ctx.treasure_counts[("A", "B", "C")] == 1
    assert ctx.best_levels[("A", "B", "C")] == (2, 1, 1)


# ---------------------------------------------------------------------------
# 扫描前跳过已处理过的基质（skip_locked_essence / skip_deprecated_essence）
# ---------------------------------------------------------------------------


def _enable_skip_marked(mock_user_setting_manager, **flags) -> None:
    """打开"扫描前跳过已处理过的基质"开关（默认两类都开）。

    ``flags`` 用于只打开其中一类，例如
    ``_enable_skip_marked(manager, skip_locked_essence=True)``。
    """
    settings = {"skip_locked_essence": True, "skip_deprecated_essence": True}
    settings.update(flags)
    mock_user_setting_manager.get_user_setting.return_value = UserSetting(**settings)


def _build_scanner_engine(ctx, user_setting_manager, profile) -> ScannerEngine:
    return ScannerEngine(
        ctx=ctx,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=user_setting_manager,
        profile=profile,
    )


def test_skip_marked_detector_not_used_when_disabled(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """开关关闭时不做任何检测，扫描行为与改动前一致。"""
    window_actions = MockWindowActions()
    engine = ScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=window_actions,
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    engine.execute(threading.Event())

    mock_scanner_context.skip_marker_detector.find_marked_cells.assert_not_called()
    assert window_actions.click_calls == [(100, 200)]


def test_skip_marked_locked_cell_is_not_clicked_nor_recognized(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """开关打开且该格被标记（锁定 / 弃用）时，不点击也不做整屏识别。"""
    _enable_skip_marked(mock_user_setting_manager)
    mock_scanner_context.skip_marker_detector.find_marked_cells.return_value = {
        (0, 0): SkipMarkerLabel.LOCKED
    }

    window_actions = MockWindowActions()
    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )
    engine._window_actions = window_actions

    engine.execute(threading.Event())

    assert window_actions.click_calls == []
    mock_scanner_context.attr_recognizer.recognize_roi.assert_not_called()


def test_skip_marked_only_locked_cells_are_skipped(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """同一页里只有被判定为已处理过的格子被跳过，其余照常扫描。"""
    _enable_skip_marked(mock_user_setting_manager)
    mock_profile.essence_icon_x_list = [100, 200]
    mock_profile.essence_icon_y_list = [200, 300]
    mock_scanner_context.skip_marker_detector.find_marked_cells.return_value = {
        (0, 1): SkipMarkerLabel.LOCKED,
        (1, 0): SkipMarkerLabel.DEPRECATED,
    }

    window_actions = MockWindowActions()
    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )
    engine._window_actions = window_actions

    engine.execute(threading.Event())

    assert window_actions.click_calls == [(100, 200), (200, 300)]


def test_skip_marked_falls_back_when_template_not_loaded(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """模板未加载时安全降级：不检测、不跳过，全部照常扫描。"""
    _enable_skip_marked(mock_user_setting_manager)
    mock_scanner_context.skip_marker_detector.loaded = False
    mock_scanner_context.skip_marker_detector.loaded_labels = set()

    window_actions = MockWindowActions()
    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )
    engine._window_actions = window_actions

    engine.execute(threading.Event())

    mock_scanner_context.skip_marker_detector.find_marked_cells.assert_not_called()
    assert window_actions.click_calls == [(100, 200)]


@pytest.mark.parametrize(
    ("flags", "expected_clicks"),
    [
        ({"skip_locked_essence": True, "skip_deprecated_essence": False}, [(200, 200)]),
        ({"skip_locked_essence": False, "skip_deprecated_essence": True}, [(100, 200)]),
        ({"skip_locked_essence": True, "skip_deprecated_essence": True}, []),
        (
            {"skip_locked_essence": False, "skip_deprecated_essence": False},
            [(100, 200), (200, 200)],
        ),
    ],
)
def test_skip_marked_switches_are_independent(
    mock_scanner_context,
    mock_user_setting_manager,
    mock_profile,
    flags,
    expected_clicks,
):
    """锁定与弃用由各自开关独立控制，关闭的那类照常点击识别。"""
    mock_profile.essence_icon_x_list = [100, 200]
    mock_profile.essence_icon_y_list = [200]

    # 第 1 列锁定、第 2 列弃用
    mock_scanner_context.skip_marker_detector.find_marked_cells.return_value = {
        (0, 0): SkipMarkerLabel.LOCKED,
        (0, 1): SkipMarkerLabel.DEPRECATED,
    }

    if not any(flags.values()):
        mock_user_setting_manager.get_user_setting.return_value = UserSetting(**flags)
    else:
        _enable_skip_marked(mock_user_setting_manager, **flags)

    window_actions = MockWindowActions()
    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )
    engine._window_actions = window_actions

    engine.execute(threading.Event())

    assert window_actions.click_calls == expected_clicks


def test_skip_marked_ignores_label_whose_template_is_missing(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """只启用弃用、但弃用模板缺失时：不跳过任何格子，也不误用锁定模板。"""
    _enable_skip_marked(
        mock_user_setting_manager,
        skip_locked_essence=False,
        skip_deprecated_essence=True,
    )
    mock_scanner_context.skip_marker_detector.loaded_labels = {SkipMarkerLabel.LOCKED}
    mock_scanner_context.skip_marker_detector.find_marked_cells.return_value = {
        (0, 0): SkipMarkerLabel.LOCKED,
    }

    window_actions = MockWindowActions()
    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )
    engine._window_actions = window_actions

    engine.execute(threading.Event())

    # 检测到了锁定标记，但用户没开锁定开关 → 仍要点击
    assert window_actions.click_calls == [(100, 200)]


def _capture_loguru_messages(action) -> list[str]:
    """捕获 loguru 日志消息。

    本项目用 loguru（``utils.log``），pytest 的 ``caplog`` 只能抓标准 logging，
    所以这里临时挂一个 sink。
    """
    from loguru import logger as loguru_logger

    messages: list[str] = []
    sink_id = loguru_logger.add(
        lambda message: messages.append(message.record["message"]), level="DEBUG"
    )
    try:
        action()
    finally:
        loguru_logger.remove(sink_id)
    return messages


def test_skip_marked_log_separates_locked_and_deprecated(
    mock_scanner_context, mock_user_setting_manager, mock_profile
):
    """扫描日志里要把已锁定与已弃用的数量分开显示。"""
    _enable_skip_marked(mock_user_setting_manager)
    mock_profile.essence_icon_x_list = [100, 200, 300]
    mock_profile.essence_icon_y_list = [200]
    mock_scanner_context.skip_marker_detector.find_marked_cells.return_value = {
        (0, 0): SkipMarkerLabel.LOCKED,
        (0, 1): SkipMarkerLabel.DEPRECATED,
        (0, 2): SkipMarkerLabel.DEPRECATED,
    }

    engine = _build_scanner_engine(
        mock_scanner_context, mock_user_setting_manager, mock_profile
    )

    messages = _capture_loguru_messages(lambda: engine.execute(threading.Event()))

    summary = [m for m in messages if "将跳过这些格子的点击与识别" in m]
    assert summary, "未输出跳过汇总日志"
    assert "1 个已锁定" in summary[0], summary[0]
    assert "2 个已弃用" in summary[0], summary[0]
    # 顺序固定为"已锁定、已弃用"，不随 set 迭代顺序变化
    assert summary[0].index("已锁定") < summary[0].index("已弃用"), summary[0]

    assert "第 1 行第 1 列的基质已锁定，跳过。" in messages
    assert "第 1 行第 2 列的基质已弃用，跳过。" in messages
    assert "第 1 行第 3 列的基质已弃用，跳过。" in messages


def test_skip_marked_scan_single_row_skips_locked_columns(
    mock_scanner_context, mock_user_setting_manager, mock_profile, monkeypatch
):
    """``_scan_single_row`` 跳过已标记的列，且跳过的格子不计入"全部重复"判定。"""
    _enable_skip_marked(mock_user_setting_manager)
    mock_profile.essence_icon_x_list = [100, 200]
    mock_profile.essence_icon_y_list = [200]

    window_actions = MockWindowActions()
    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=window_actions,
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    recognized: list[int] = []

    # _scan_single_row 依赖 _execute_grid_scan 初始化的运行时状态
    engine._scanned_essence_hashes = set()
    from endfield_essence_recognizer.core.scanner.claimer import ClaimContext

    engine._claim_context = ClaimContext(
        [],
        mock_user_setting_manager.get_user_setting(),
        mock_scanner_context.static_game_data,
    )

    def fake_recognize_essence(image_source, ctx, profile):
        recognized.append(len(recognized))
        from endfield_essence_recognizer.core.scanner.models import EssenceData

        return EssenceData(
            stats=[None, None, None],
            stat_types=[None, None, None],
            levels=[None, None, None],
            rarity=RarityLabel.OTHER,
            abandon_label=AbandonStatusLabel.NOT_ABANDONED,
            lock_label=LockStatusLabel.NOT_LOCKED,
        )

    monkeypatch.setattr(
        scanner_engine_module, "recognize_essence", fake_recognize_essence
    )

    result = engine._scan_single_row(
        0,
        threading.Event(),
        mock_user_setting_manager.get_user_setting(),
        mock_profile.essence_icon_x_list,
        mock_profile.essence_icon_y_list,
        {(0, 0): SkipMarkerLabel.LOCKED},
    )

    # 只点击并识别了未锁定的第 2 列
    assert window_actions.click_calls == [(200, 200)]
    assert len(recognized) == 1
    # 跳过的格子不参与重复判定
    assert result is False


def test_skip_marked_draggable_detects_once_per_page_and_after_overscroll(
    mock_scanner_context, mock_user_setting_manager, mock_profile, monkeypatch
):
    """自动翻页时每页检测一次；过冲微调后内容位置改变，必须重新检测。"""
    setting = UserSetting(
        auto_page_flip=True,
        skip_locked_essence=True,
        skip_deprecated_essence=True,
    )
    setting.fix_page_flip_overscroll = True
    mock_user_setting_manager.get_user_setting.return_value = setting

    mock_profile.essence_icon_x_list = [100]
    mock_profile.essence_icon_y_list = [200, 300]
    mock_profile.DRAG_START_POS = Point(100, 900)
    mock_profile.DRAG_END_POS = Point(100, 100)
    mock_profile.SCROLLBAR_CHECK_POS = None

    engine = DraggableScannerEngine(
        ctx=mock_scanner_context,
        image_source=MockImageSource(),
        window_actions=MockWindowActions(),
        user_setting_manager=mock_user_setting_manager,
        profile=mock_profile,
    )

    monkeypatch.setattr(scanner_engine_module, "check_scene", lambda *_args: True)
    monkeypatch.setattr(engine, "_scan_current_page", MagicMock())
    monkeypatch.setattr(engine, "_scan_single_row", MagicMock(return_value=True))
    monkeypatch.setattr(engine, "_correct_overscroll", MagicMock())
    monkeypatch.setattr(
        engine,
        "_progressive_drag",
        MagicMock(side_effect=[(800, False), (100, True)]),
    )
    monkeypatch.setattr(
        engine, "_check_scrollbar_at_bottom", MagicMock(return_value=False)
    )

    engine.execute(threading.Event())

    detector = mock_scanner_context.skip_marker_detector
    # 第 1 页 1 次 + 第 2 页 1 次 + 过冲微调后重测 1 次 + 第 3 页（末页）1 次
    assert detector.find_marked_cells.call_count == 4
