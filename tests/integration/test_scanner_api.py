from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.dependencies import (
    get_delivery_claimer_engine_dep,
    get_one_time_recognition_engine_dep,
    get_scanner_engine_dep,
    get_scanner_service,
    require_game_or_webview_is_active,
    require_game_window_exists,
)
from endfield_essence_recognizer.server import app
from endfield_essence_recognizer.services.scanner_service import ScannerService


@pytest.fixture
def mock_scanner_service():
    """Mock ScannerService to avoid starting real threads."""
    service = ScannerService()
    service.start_scan = MagicMock()
    service.stop_scan = MagicMock()
    service.toggle_scan = MagicMock()
    service.is_running = MagicMock(return_value=False)
    return service


@pytest.fixture
def client(mock_scanner_service):
    """FastAPI TestClient with overridden dependencies."""
    app.dependency_overrides[get_scanner_service] = lambda: mock_scanner_service
    # Mock engines to avoid real initialization
    # use explicit lambdas to avoid fastapi caching MagicMock instance
    app.dependency_overrides[get_scanner_engine_dep] = lambda: MagicMock()
    app.dependency_overrides[get_one_time_recognition_engine_dep] = lambda: MagicMock()
    app.dependency_overrides[get_delivery_claimer_engine_dep] = lambda: MagicMock()

    # Bypass window checks
    app.dependency_overrides[require_game_window_exists] = lambda: None
    app.dependency_overrides[require_game_or_webview_is_active] = lambda: None

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_recognize_once_endpoint(client, mock_scanner_service):
    """Test POST /api/recognize_once."""
    response = client.post("/api/recognize_once")
    assert response.status_code == 200
    assert mock_scanner_service.start_scan.called


def test_start_scanning_endpoint(client, mock_scanner_service):
    """Test POST /api/start_scanning."""
    response = client.post("/api/start_scanning")
    # This is the original endpoint used by the frontend
    assert response.status_code == 200
    assert mock_scanner_service.toggle_scan.called


def test_toggle_scanning_essence(client, mock_scanner_service):
    """Test POST /api/toggle_scanning for essence."""
    response = client.post("/api/toggle_scanning", json={"task_type": "essence"})
    assert response.status_code == 200
    assert mock_scanner_service.toggle_scan.called


def test_toggle_scanning_delivery(client, mock_scanner_service):
    """Test POST /api/toggle_scanning for delivery_claim."""
    response = client.post("/api/toggle_scanning", json={"task_type": "delivery_claim"})
    assert response.status_code == 200
    assert mock_scanner_service.toggle_scan.called


def test_toggle_scanning_invalid(client):
    """Test POST /api/toggle_scanning with invalid task type."""
    response = client.post("/api/toggle_scanning", json={"task_type": "invalid"})
    assert response.status_code == 422
