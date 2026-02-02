from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from endfield_essence_recognizer.core.window.manager import WindowManager


@pytest.fixture
def window_manager():
    return WindowManager(["Test Window"])


@pytest.fixture
def mock_window():
    win = MagicMock()
    # Mock pygetwindow.Window.isActive
    win.isActive = True
    return win


def test_window_target_exists(window_manager, mock_window):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = mock_window
        assert window_manager.target_exists is True
        mock_get_support.assert_called_once_with(["Test Window"])

        # Second call should use cache
        assert window_manager.target_exists is True
        mock_get_support.assert_called_once()


def test_window_not_target_exists(window_manager):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = None
        assert window_manager.target_exists is False


def test_window_target_is_active(window_manager, mock_window):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = mock_window
        mock_window.isActive = True
        assert window_manager.target_is_active is True
        mock_window.isActive = False
        assert window_manager.target_is_active is False


def test_window_is_not_active_no_window(window_manager):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = None
        assert window_manager.target_is_active is False


def test_restore(window_manager, mock_window):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = mock_window

        # Test already restored
        mock_window.isMinimized = False
        assert window_manager.restore() is False
        mock_window.restore.assert_not_called()

        # Test needs restoring
        mock_window.isMinimized = True
        assert window_manager.restore() is True
        mock_window.restore.assert_called_once()


def test_activate(window_manager, mock_window):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = mock_window

        # Test already active
        mock_window.isActive = True
        assert window_manager.activate() is False
        mock_window.activate.assert_not_called()

        # Test needs activation
        mock_window.isActive = False
        assert window_manager.activate() is True
        mock_window.activate.assert_called_once()


def test_clear(window_manager, mock_window):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = mock_window

        assert window_manager.target_exists is True
        mock_get_support.assert_called_once()

        window_manager.clear()
        assert window_manager.target_exists is True
        assert mock_get_support.call_count == 2


def test_get_client_size(window_manager, mock_window):
    with (
        patch(
            "endfield_essence_recognizer.core.window.manager.get_support_window"
        ) as mock_get_support,
        patch(
            "endfield_essence_recognizer.core.window.manager.get_client_size"
        ) as mock_utils_get_size,
    ):
        mock_get_support.return_value = mock_window
        mock_utils_get_size.return_value = (1920, 1080)

        size = window_manager.get_client_size()
        assert size == (1920, 1080)
        mock_utils_get_size.assert_called_once_with(mock_window)


def test_get_client_size_no_window(window_manager):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = None
        with pytest.raises(RuntimeError, match="No window found"):
            window_manager.get_client_size()


def test_screenshot(window_manager, mock_window):
    mock_image = np.zeros((100, 100, 3), dtype=np.uint8)

    with (
        patch(
            "endfield_essence_recognizer.core.window.manager.get_support_window"
        ) as mock_get_support,
        patch(
            "endfield_essence_recognizer.core.window.manager.screenshot_window"
        ) as mock_screenshot,
    ):
        mock_get_support.return_value = mock_window
        mock_screenshot.return_value = mock_image

        # Test without ROI
        res = window_manager.screenshot()
        assert res is mock_image
        mock_screenshot.assert_called_with(mock_window, None)

        # Test with ROI
        roi = ((0, 0), (10, 10))
        window_manager.screenshot(roi)
        mock_screenshot.assert_called_with(mock_window, roi)


def test_screenshot_no_window(window_manager):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = None
        with pytest.raises(RuntimeError, match="No window found"):
            window_manager.screenshot()


def test_click(window_manager, mock_window):
    with (
        patch(
            "endfield_essence_recognizer.core.window.manager.get_support_window"
        ) as mock_get_support,
        patch(
            "endfield_essence_recognizer.core.window.manager.click_on_window"
        ) as mock_click,
    ):
        mock_get_support.return_value = mock_window

        window_manager.click(100, 200)
        mock_click.assert_called_once_with(mock_window, 100, 200)


def test_click_no_window(window_manager):
    with patch(
        "endfield_essence_recognizer.core.window.manager.get_support_window"
    ) as mock_get_support:
        mock_get_support.return_value = None
        with pytest.raises(RuntimeError, match="No window found"):
            window_manager.click(100, 200)
