import threading
from unittest.mock import MagicMock

import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusLabel,
    AttributeLevelRecognizer,
    LockStatusLabel,
)
from endfield_essence_recognizer.core.recognition.recognizer import Recognizer
from endfield_essence_recognizer.core.recognition.tasks.ui import UISceneLabel
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.scanner.engine import ScannerEngine
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


class MockImageSource:
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height

    def get_client_size(self):
        return self.width, self.height

    def screenshot(self, relative_region=None):
        # Return a dummy black image
        if relative_region:
            w = relative_region.w
            h = relative_region.h
        else:
            w, h = self.width, self.height
        return np.zeros((h, w, 3), dtype=np.uint8)


class MockWindowActions:
    def __init__(self):
        self._target_exists = True
        self._target_is_active = True
        self.click_calls = []

    @property
    def target_exists(self):
        return self._target_exists

    @property
    def target_is_active(self):
        return self._target_is_active

    def restore(self):
        return True

    def activate(self):
        return True

    def show(self):
        return True

    def click(self, x, y):
        self.click_calls.append((x, y))

    def wait(self, seconds):
        pass


@pytest.fixture
def mock_scanner_context():
    # Mock recognizers
    ui_scene_recognizer = MagicMock(spec=Recognizer)
    ui_scene_recognizer.recognize_roi_fallback.return_value = (
        UISceneLabel.ESSENCE_UI,
        1.0,
    )

    attr_recognizer = MagicMock(spec=Recognizer)
    attr_recognizer.recognize_roi.return_value = ("atk", 0.9)  # Dummy attribute

    attr_level_recognizer = MagicMock(spec=AttributeLevelRecognizer)
    attr_level_recognizer.recognize_level.return_value = 10

    abandon_status_recognizer = MagicMock(spec=Recognizer)
    abandon_status_recognizer.recognize_roi_fallback.return_value = (
        AbandonStatusLabel.NOT_ABANDONED,
        0.9,
    )

    lock_status_recognizer = MagicMock(spec=Recognizer)
    lock_status_recognizer.recognize_roi_fallback.return_value = (
        LockStatusLabel.NOT_LOCKED,
        0.9,
    )

    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
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
    profile.ESSENCE_UI_ROI = MagicMock()
    profile.ESSENCE_UI_ROI.w = 100
    profile.ESSENCE_UI_ROI.h = 100

    # Mock just one essence icon for simplicity
    profile.essence_icon_x_list = [100]
    profile.essence_icon_y_list = [200]
    profile.STATS_0_ROI = MagicMock()
    profile.STATS_0_ROI.w = 50
    profile.STATS_0_ROI.h = 50
    profile.STATS_1_ROI = MagicMock()
    profile.STATS_1_ROI.w = 50
    profile.STATS_1_ROI.h = 50
    profile.STATS_2_ROI = MagicMock()
    profile.STATS_2_ROI.w = 50
    profile.STATS_2_ROI.h = 50
    profile.DEPRECATE_BUTTON_ROI = MagicMock()
    profile.DEPRECATE_BUTTON_ROI.w = 30
    profile.DEPRECATE_BUTTON_ROI.h = 30
    profile.LOCK_BUTTON_ROI = MagicMock()
    profile.LOCK_BUTTON_ROI.w = 30
    profile.LOCK_BUTTON_ROI.h = 30

    profile.LOCK_BUTTON_POS = MagicMock(x=10, y=10)
    profile.DEPRECATE_BUTTON_POS = MagicMock(x=20, y=20)
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
