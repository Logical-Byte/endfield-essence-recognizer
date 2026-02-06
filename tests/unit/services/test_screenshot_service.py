from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.models.screenshot import (
    ImageFormat,
    ScreenshotSaveFormat,
)
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService


@pytest.fixture
def mock_window_manager():
    wm = MagicMock()
    wm.target_is_active = True
    wm.target_exists = True
    wm.screenshot.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
    wm.show.return_value = True
    wm.restore.return_value = True
    wm.activate.return_value = True
    return wm


@pytest.fixture
def screenshot_service(mock_window_manager):
    return ScreenshotService(mock_window_manager)


@pytest.mark.asyncio
async def test_capture_as_data_uri_success(screenshot_service, mock_window_manager):
    with (
        patch(
            "endfield_essence_recognizer.services.screenshot_service.cv2.resize"
        ) as mock_resize,
        patch(
            "endfield_essence_recognizer.services.screenshot_service.image_to_data_uri"
        ) as mock_to_uri,
    ):
        mock_resize.return_value = np.zeros((360, 640, 3), dtype=np.uint8)
        mock_to_uri.return_value = "data:image/jpeg;base64,dummy"

        result = await screenshot_service.capture_as_data_uri(
            width=640, height=360, format=ImageFormat.JPG
        )

        assert result == "data:image/jpeg;base64,dummy"
        mock_window_manager.screenshot.assert_called_once()
        mock_resize.assert_called_once()
        mock_to_uri.assert_called_once()


@pytest.mark.asyncio
async def test_capture_as_data_uri_inactive(screenshot_service, mock_window_manager):
    mock_window_manager.target_is_active = False

    result = await screenshot_service.capture_as_data_uri()

    assert result is None
    mock_window_manager.screenshot.assert_not_called()


@pytest.mark.asyncio
async def test_capture_and_save_success(screenshot_service, mock_window_manager):
    mock_res_profile = MagicMock(spec=ResolutionProfile)
    mock_res_profile.MASK_ESSENCE_REGION_UID = MagicMock()
    mock_res_profile.MASK_ESSENCE_REGION_CURRENCY = MagicMock()
    mock_dir = Path("/mock/dir")

    with (
        patch(
            "endfield_essence_recognizer.services.screenshot_service.save_image"
        ) as mock_save,
        patch(
            "endfield_essence_recognizer.services.screenshot_service.mask_region"
        ) as mock_mask,
    ):
        full_path, file_name = await screenshot_service.capture_and_save(
            screenshot_dir=mock_dir,
            resolution_profile=mock_res_profile,
            should_focus=True,
            post_process=True,
            title="Test",
            fmt=ScreenshotSaveFormat.PNG,
        )

        assert "Test" in file_name
        assert full_path.startswith(str(mock_dir))
        mock_window_manager.activate.assert_called_once()
        mock_mask.assert_called()  # Should call for UID and Currency
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_capture_and_save_not_exists(screenshot_service, mock_window_manager):
    mock_window_manager.target_exists = False

    with pytest.raises(RuntimeError, match="Game window not found"):
        await screenshot_service.capture_and_save(
            screenshot_dir=Path("."), resolution_profile=MagicMock()
        )


@pytest.mark.asyncio
async def test_capture_and_save_no_focus_no_post(
    screenshot_service, mock_window_manager
):
    mock_res_profile = MagicMock(spec=ResolutionProfile)
    mock_dir = Path("/mock/dir")

    with (
        patch(
            "endfield_essence_recognizer.services.screenshot_service.save_image"
        ) as mock_save,
        patch(
            "endfield_essence_recognizer.services.screenshot_service.mask_region"
        ) as mock_mask,
    ):
        await screenshot_service.capture_and_save(
            screenshot_dir=mock_dir,
            resolution_profile=mock_res_profile,
            should_focus=False,
            post_process=False,
        )

        mock_window_manager.activate.assert_not_called()
        mock_mask.assert_not_called()
        mock_save.assert_called_once()
