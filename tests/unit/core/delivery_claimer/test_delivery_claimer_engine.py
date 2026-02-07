import threading
from unittest.mock import MagicMock, call

import pytest

from endfield_essence_recognizer.core.delivery_claimer.engine import (
    DeliveryClaimerEngine,
)
from endfield_essence_recognizer.core.layout.base import Point, Region
from endfield_essence_recognizer.core.recognition.tasks.delivery_job_reward import (
    DeliveryJobRewardLabel,
)
from endfield_essence_recognizer.core.recognition.tasks.delivery_ui import (
    DeliverySceneLabel,
)


@pytest.fixture
def mock_image_source():
    source = MagicMock()
    source.get_client_size.return_value = (1920, 1080)
    source.screenshot.return_value = "dummy_image"
    return source


@pytest.fixture
def mock_window_actions():
    actions = MagicMock()
    actions.target_is_active = True
    actions.activate.return_value = True
    actions.show.return_value = True
    actions.wait = MagicMock()
    return actions


@pytest.fixture
def mock_profile():
    profile = MagicMock()
    profile.RESOLUTION = (1920, 1080)
    profile.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI = Region(Point(0, 0), Point(100, 100))
    profile.DELIVERY_JOB_REWARD_ROI = Region(Point(50, 50), Point(150, 150))
    profile.DELIVERY_JOB_REFRESH_BUTTON_POINT = Point(1000, 500)
    return profile


@pytest.fixture
def mock_delivery_scene_recognizer():
    recognizer = MagicMock()
    recognizer.recognize_roi_fallback.return_value = (
        DeliverySceneLabel.LIST_OF_DELIVERY_JOBS,
        0.9,
    )
    return recognizer


@pytest.fixture
def mock_delivery_job_reward_recognizer():
    recognizer = MagicMock()
    recognizer.recognize_roi_fallback.return_value = (
        DeliveryJobRewardLabel.UNKNOWN,
        0.5,
    )
    return recognizer


@pytest.fixture
def mock_audio_service():
    return MagicMock()


@pytest.fixture
def engine(
    mock_image_source,
    mock_window_actions,
    mock_profile,
    mock_delivery_scene_recognizer,
    mock_delivery_job_reward_recognizer,
    mock_audio_service,
):
    return DeliveryClaimerEngine(
        mock_image_source,
        mock_window_actions,
        mock_profile,
        mock_delivery_scene_recognizer,
        mock_delivery_job_reward_recognizer,
        mock_audio_service,
    )


def test_execute_initial_scene_check_fails_resolution(
    engine, mock_image_source, mock_profile
):
    """Test that execution stops immediately if window resolution doesn't match profile.

    When the client size doesn't match the configured resolution, _check_scene returns
    False and no scene verification screenshot is taken.
    """
    mock_image_source.get_client_size.return_value = (1280, 720)
    stop_event = threading.Event()

    engine.execute(stop_event)

    mock_image_source.screenshot.assert_not_called()


def test_execute_initial_scene_check_fails_wrong_scene(
    engine, mock_image_source, mock_delivery_scene_recognizer, mock_profile
):
    """Test that execution stops if the current scene is not the delivery job list.

    Verifies that a single scene check screenshot is taken, and execution stops
    without proceeding to reward scanning.
    """
    mock_delivery_scene_recognizer.recognize_roi_fallback.return_value = (
        DeliverySceneLabel.UNKNOWN,
        0.5,
    )
    stop_event = threading.Event()

    engine.execute(stop_event)

    mock_image_source.screenshot.assert_called_once_with(
        mock_profile.LIST_OF_DELIVERY_JOBS_SCENE_CHECK_ROI
    )
    assert mock_image_source.screenshot.call_count == 1


def test_execute_window_inactive_stops(engine, mock_window_actions):
    """Test that the loop breaks immediately if the window becomes inactive.

    Verifies that when the window is not active during loop iteration, execution
    breaks without performing scene checks or reward scans.
    """
    mock_window_actions.target_is_active = False
    stop_event = threading.Event()

    engine.execute(stop_event)

    mock_window_actions.activate.assert_called()
    mock_window_actions.show.assert_called()
    assert not engine._image_source.screenshot.called


def test_execute_success_first_try(
    engine,
    mock_image_source,
    mock_delivery_job_reward_recognizer,
    mock_audio_service,
    mock_profile,
):
    """Test successful ticket claim on the first reward scan attempt.

    Verifies that when the ticket is found immediately, the engine takes exactly
    two screenshots (scene check and reward scan), uses the correct ROI for reward
    scanning, and plays the success notification.
    """
    mock_delivery_job_reward_recognizer.recognize_roi_fallback.return_value = (
        DeliveryJobRewardLabel.WULING_DISPATCH_TICKET,
        0.9,
    )
    stop_event = threading.Event()

    engine.execute(stop_event)

    assert mock_image_source.screenshot.call_count == 2
    mock_image_source.screenshot.assert_any_call(mock_profile.DELIVERY_JOB_REWARD_ROI)
    mock_audio_service.play_enable.assert_called_once()


def test_execute_retry_then_success(
    engine,
    mock_image_source,
    mock_delivery_job_reward_recognizer,
    mock_window_actions,
    mock_profile,
    mock_audio_service,
):
    """Test the retry flow when ticket is not found on first attempt.

    Verifies that when the initial scan finds no ticket, the engine waits for the
    click interval (minus safety buffer), clicks the refresh button, waits a short
    buffer, and retries the scan. On the second attempt, the ticket is found and
    the success notification plays.
    """
    mock_delivery_job_reward_recognizer.recognize_roi_fallback.side_effect = [
        (DeliveryJobRewardLabel.UNKNOWN, 0.5),
        (DeliveryJobRewardLabel.WULING_DISPATCH_TICKET, 0.9),
    ]
    stop_event = threading.Event()

    engine.execute(stop_event)

    mock_window_actions.click.assert_called_once_with(
        mock_profile.DELIVERY_JOB_REFRESH_BUTTON_POINT.x,
        mock_profile.DELIVERY_JOB_REFRESH_BUTTON_POINT.y,
    )
    mock_window_actions.wait.assert_has_calls(
        [call(0.5), call(0.5), call(3.0), call(2.0)]
    )
    mock_audio_service.play_enable.assert_called_once()
    assert mock_image_source.screenshot.call_count == 5


def test_execute_stop_event(
    engine, mock_delivery_job_reward_recognizer, mock_window_actions
):
    """Test that execution respects the stop_event during the retry loop.

    Simulates the stop event being set during the wait after an unsuccessful
    scan. Verifies that the loop breaks before attempting the refresh click.
    """
    mock_delivery_job_reward_recognizer.recognize_roi_fallback.return_value = (
        DeliveryJobRewardLabel.UNKNOWN,
        0.5,
    )
    stop_event = threading.Event()

    def set_stop(*args):
        stop_event.set()

    mock_window_actions.wait.side_effect = set_stop

    engine.execute(stop_event)

    mock_window_actions.click.assert_not_called()
