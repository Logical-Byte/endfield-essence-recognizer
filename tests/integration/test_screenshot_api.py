from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.deps import (
    get_screenshot_service,
    get_screenshots_dir_dep,
)
from endfield_essence_recognizer.server import app


@pytest.fixture
def mock_screenshot_service():
    service = MagicMock()
    service.capture_as_data_uri = AsyncMock()
    service.capture_and_save = AsyncMock()
    return service


@pytest.fixture
def client(mock_screenshot_service, tmp_path):
    # Override ScreenshotService
    app.dependency_overrides[get_screenshot_service] = lambda: mock_screenshot_service
    # Override Screenshots Dir
    app.dependency_overrides[get_screenshots_dir_dep] = lambda: tmp_path

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_screenshot_success(client, mock_screenshot_service):
    """Test GET /api/screenshot returns a data URI when window is active."""
    mock_screenshot_service.capture_as_data_uri.return_value = (
        "data:image/jpeg;base64,mock_data"
    )

    response = client.get("/api/screenshot?width=640&height=360&format=jpg&quality=50")

    assert response.status_code == 200
    assert response.json() == "data:image/jpeg;base64,mock_data"
    mock_screenshot_service.capture_as_data_uri.assert_called_once()


def test_get_screenshot_inactive(client, mock_screenshot_service):
    """Test GET /api/screenshot returns null when window is inactive."""
    mock_screenshot_service.capture_as_data_uri.return_value = None

    response = client.get("/api/screenshot")

    assert response.status_code == 200
    assert response.json() is None


def test_take_and_save_screenshot_success(client, mock_screenshot_service, tmp_path):
    """Test POST /api/take_and_save_screenshot saves a file and returns success."""
    mock_path = str(tmp_path / "Endfield_mock.png")
    mock_screenshot_service.capture_and_save.return_value = (
        mock_path,
        "Endfield_mock.png",
    )

    payload = {
        "should_focus": True,
        "post_process": True,
        "title": "IntegrationTest",
        "format": "png",
    }

    response = client.post("/api/take_and_save_screenshot", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_name"] == "Endfield_mock.png"
    assert data["file_path"] == mock_path


def test_take_and_save_screenshot_error(client, mock_screenshot_service):
    """Test POST /api/take_and_save_screenshot handles errors gracefully."""
    mock_screenshot_service.capture_and_save.side_effect = Exception("Unexpected Error")

    payload = {
        "should_focus": True,
        "post_process": True,
        "title": "ErrorTest",
        "format": "jpg",
    }

    response = client.post("/api/take_and_save_screenshot", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Unexpected Error" in data["message"]


def test_take_and_save_screenshot_invalid_title(client):
    """Test POST /api/take_and_save_screenshot with invalid title characters."""
    # Test with underscore (explicitly forbidden), space, and path traversal
    for invalid_title in [
        "Endfield_1",
        "My Screenshot",
        "../traversal",
        "test_title",
        "!",
        "@",
    ]:
        payload = {
            "should_focus": True,
            "post_process": True,
            "title": invalid_title,
            "format": "png",
        }
        response = client.post("/api/take_and_save_screenshot", json=payload)
        assert response.status_code == 422
