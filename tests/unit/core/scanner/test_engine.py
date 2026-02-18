import threading
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
)
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.recognition.template_recognizer import (
    TemplateRecognizer,
)
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.scanner.engine import ScannerEngine
from endfield_essence_recognizer.schemas.user_setting import UserSetting
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

    static_game_data = MagicMock()
    # Mock return value for get_stat to avoid errors when formatting logs
    static_game_data.get_stat.return_value = MagicMock(name="TestStat")

    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
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
