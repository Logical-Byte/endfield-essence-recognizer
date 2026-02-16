"""Tests for WindowManager drag functionality."""

from unittest.mock import MagicMock, patch

import pytest

from endfield_essence_recognizer.core.window.manager import WindowManager
from endfield_essence_recognizer.exceptions import WindowNotFoundError


class TestWindowManagerDrag:
    """Tests for WindowManager.drag method."""

    def test_drag_success(self):
        """Test successful drag operation with default parameters."""
        manager = WindowManager(["Test Window"])
        mock_window = MagicMock()

        with patch.object(
            manager, "_get_window", return_value=mock_window
        ) as mock_get_window:
            with patch(
                "endfield_essence_recognizer.core.window.manager.drag_on_window"
            ) as mock_drag:
                manager.drag(100, 200, 300, 400)

                mock_get_window.assert_called_once()
                mock_drag.assert_called_once_with(
                    mock_window, 100, 200, 300, 400, 0.5, 0.5
                )

    def test_drag_with_custom_parameters(self):
        """Test drag with custom duration and hold_time."""
        manager = WindowManager(["Test Window"])
        mock_window = MagicMock()

        with patch.object(manager, "_get_window", return_value=mock_window):
            with patch(
                "endfield_essence_recognizer.core.window.manager.drag_on_window"
            ) as mock_drag:
                manager.drag(0, 0, 100, 100, duration=1.0, hold_time=0.3)

                mock_drag.assert_called_once_with(mock_window, 0, 0, 100, 100, 1.0, 0.3)

    def test_drag_window_not_found(self):
        """Test drag raises WindowNotFoundError when window is None."""
        manager = WindowManager(["Test Window"])

        with patch.object(manager, "_get_window", return_value=None):
            with pytest.raises(WindowNotFoundError):
                manager.drag(100, 200, 300, 400)

    def test_drag_vertical_scroll(self):
        """Test vertical drag (scrolling up)."""
        manager = WindowManager(["Test Window"])
        mock_window = MagicMock()

        with patch.object(manager, "_get_window", return_value=mock_window):
            with patch(
                "endfield_essence_recognizer.core.window.manager.drag_on_window"
            ) as mock_drag:
                # Drag from bottom to top (scrolling up)
                manager.drag(500, 800, 500, 100, duration=1.0, hold_time=0.3)

                mock_drag.assert_called_once_with(
                    mock_window, 500, 800, 500, 100, 1.0, 0.3
                )
