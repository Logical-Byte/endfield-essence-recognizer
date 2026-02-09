import json

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.dependencies import get_user_setting_manager_dep
from endfield_essence_recognizer.server import app
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


@pytest.fixture
def test_settings_file(tmp_path):
    """Fixture for a temporary settings file."""
    return tmp_path / "test_settings.json"


@pytest.fixture
def test_manager(test_settings_file):
    """Fixture for a UserSettingManager instance using a temporary file."""
    return UserSettingManager(test_settings_file)


@pytest.fixture
def client(test_manager):
    """Fixture for a FastAPI TestClient with overridden dependencies."""

    def override_get_user_setting_manager():
        return test_manager

    app.dependency_overrides[get_user_setting_manager_dep] = (
        override_get_user_setting_manager
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_get_config(client, test_manager):
    """Test the GET /api/config endpoint."""
    # Setup initial setting
    test_manager.update_from_dict({"trash_weapon_ids": ["test_weapon_api"]})

    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["trash_weapon_ids"] == ["test_weapon_api"]
    assert "version" in data


def test_post_config(client, test_manager, test_settings_file):
    """Test the POST /api/config endpoint."""
    new_config = {
        "trash_weapon_ids": ["new_weapon_from_api"],
        "treasure_action": "keep",
    }

    response = client.post("/api/config", json=new_config)
    assert response.status_code == 200
    data = response.json()
    assert data["trash_weapon_ids"] == ["new_weapon_from_api"]
    assert data["treasure_action"] == "keep"

    # Verify persistence
    assert test_settings_file.exists()
    file_data = json.loads(test_settings_file.read_text(encoding="utf-8"))
    assert file_data["trash_weapon_ids"] == ["new_weapon_from_api"]


def test_post_config_invalid_data(client):
    """Test the POST /api/config endpoint with invalid data."""
    invalid_config = {"trash_weapon_ids": "not a list"}

    response = client.post("/api/config", json=invalid_config)
    # FastAPI returns 422 Unprocessable Entity for Pydantic validation errors
    assert response.status_code == 422


def test_post_config_version_mismatch(client, test_manager):
    """Test the POST /api/config endpoint with a version mismatch."""
    from endfield_essence_recognizer.models.user_setting import UserSetting

    config_with_wrong_version = {
        "version": -1,
        "trash_weapon_ids": ["test"],
    }

    response = client.post("/api/config", json=config_with_wrong_version)
    assert response.status_code == 400
    assert "version mismatch" in response.json()["detail"].lower()
    assert str(UserSetting._VERSION) in response.json()["detail"]
    assert "-1" in response.json()["detail"]
