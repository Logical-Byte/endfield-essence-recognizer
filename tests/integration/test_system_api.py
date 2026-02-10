from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.dependencies import get_system_service
from endfield_essence_recognizer.server import app
from endfield_essence_recognizer.services.system_service import SystemService


@pytest.fixture
def mock_system_service():
    service = MagicMock(spec=SystemService)
    return service


@pytest.fixture
def client(mock_system_service):
    app.dependency_overrides[get_system_service] = lambda: mock_system_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_exit_endpoint(client, mock_system_service):
    """Test POST /api/exit."""
    response = client.post("/api/exit")
    assert response.status_code == 200
    assert mock_system_service.exit_application.called
