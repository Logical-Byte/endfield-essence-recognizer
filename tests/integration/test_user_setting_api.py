import json

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_user_setting_manager_dep
from endfield_essence_recognizer.schemas.profile import TreasureMatrixEntry
from endfield_essence_recognizer.server import app
from endfield_essence_recognizer.services.profile_manager import ProfileManager
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
def test_profile_manager(tmp_path):
    """使用临时文件的账号管理器。

    保存配置会顺带剪除失效的自定义基质引用，若不隔离，测试会直接改写
    开发者本机的 profiles.json。
    """
    manager = ProfileManager(tmp_path / "profiles.json")
    manager.load()
    return manager


@pytest.fixture
def client(test_manager, test_profile_manager):
    """Fixture for a FastAPI TestClient with overridden dependencies."""

    def override_get_user_setting_manager():
        return test_manager

    def override_get_profile_manager():
        return test_profile_manager

    app.dependency_overrides[get_user_setting_manager_dep] = (
        override_get_user_setting_manager
    )
    app.dependency_overrides[get_profile_manager] = override_get_profile_manager
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
    from endfield_essence_recognizer.schemas.user_setting import UserSetting

    config_with_wrong_version = {
        "version": -1,
        "trash_weapon_ids": ["test"],
    }

    response = client.post("/api/config", json=config_with_wrong_version)
    assert response.status_code == 400
    assert "version mismatch" in response.json()["detail"].lower()
    assert str(UserSetting._VERSION) in response.json()["detail"]
    assert "-1" in response.json()["detail"]


def _seed_custom_refs(manager: ProfileManager) -> None:
    """写入两条自定义基质引用和一条普通武器引用。"""
    manager.update_treasure_matrix(
        [
            TreasureMatrixEntry(
                weapon_id="custom:live", weapon_name="L", affix1_level=3, priority=5
            ),
            TreasureMatrixEntry(
                weapon_id="custom:gone", weapon_name="G", affix1_level=2, priority=3
            ),
            TreasureMatrixEntry(
                weapon_id="wpn_normal", weapon_name="N", affix1_level=1, priority=4
            ),
        ]
    )


def test_post_config_prunes_deleted_custom_stat_refs(client, test_profile_manager):
    """删掉一条自定义基质后保存，profile 里指向它的条目一并移除。"""
    _seed_custom_refs(test_profile_manager)

    response = client.post(
        "/api/config",
        json={
            "treasure_essence_stats": [
                {"id": "live", "name": "保留", "attribute": None}
            ]
        },
    )
    assert response.status_code == 200

    profile = test_profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "custom:live",
        "wpn_normal",
    ]
    assert profile.weapon_priorities == {"custom:live": 5, "wpn_normal": 4}


def test_post_config_keeps_refs_of_live_custom_stats(client, test_profile_manager):
    """自定义基质都还在时，保存配置不得动 profile。"""
    _seed_custom_refs(test_profile_manager)

    response = client.post(
        "/api/config",
        json={
            "treasure_essence_stats": [
                {"id": "live", "name": "A", "attribute": None},
                {"id": "gone", "name": "B", "attribute": None},
            ]
        },
    )
    assert response.status_code == 200

    profile = test_profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == [
        "custom:live",
        "custom:gone",
        "wpn_normal",
    ]


def test_reset_config_prunes_all_custom_stat_refs(client, test_profile_manager):
    """重置配置清空自定义基质，profile 中所有 custom 引用一并移除。"""
    _seed_custom_refs(test_profile_manager)

    response = client.post("/api/config/reset")
    assert response.status_code == 200

    profile = test_profile_manager.get_active_profile()
    assert [e.weapon_id for e in profile.treasure_matrix] == ["wpn_normal"]
    assert profile.weapon_priorities == {"wpn_normal": 4}
