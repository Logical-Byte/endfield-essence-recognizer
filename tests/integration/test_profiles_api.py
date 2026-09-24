"""profiles API 集成测试。"""

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_static_game_data
from endfield_essence_recognizer.server import app
from endfield_essence_recognizer.services.profile_manager import ProfileManager


class _FakeStaticGameData:
    """最小 StaticGameData 替身：自定义武器路径不依赖真实游戏数据。"""

    def get_weapon(self, weapon_id: str) -> None:
        return None


@pytest.fixture
def client(tmp_path):
    """使用临时 profile 文件并替换静态数据依赖的 TestClient。"""

    def override_get_profile_manager() -> ProfileManager:
        return manager

    manager = ProfileManager(tmp_path / "profiles.json")
    manager.load()
    app.dependency_overrides[get_profile_manager] = override_get_profile_manager
    app.dependency_overrides[get_static_game_data] = _FakeStaticGameData
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _post_batch(client, weapon_id: str):
    return client.post(
        "/api/profiles/farming_recommendations",
        json={
            "items": [
                {
                    "weapon_id": weapon_id,
                    "current_levels": [1, 1, 1],
                    "target_levels": [6, 6, 3],
                }
            ]
        },
    )


def test_batch_farming_new_custom_id_returns_recommendation(client):
    """新格式自定义武器（custom:xxx）必须被识别，而非返回 Weapon not found。"""
    response = _post_batch(client, "custom:abcd1234")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["error"] is None
    assert results[0]["recommendation"] is not None


def test_batch_farming_legacy_custom_id_returns_recommendation(client):
    """旧格式自定义武器（custom_stat_N）在迁移完成前也应能识别。"""
    response = _post_batch(client, "custom_stat_0")
    assert response.status_code == 200
    results = response.json()
    assert results[0]["error"] is None
    assert results[0]["recommendation"] is not None


def test_batch_farming_unknown_weapon_returns_error(client):
    """未知武器返回明确的 error，而不是崩溃。"""
    response = _post_batch(client, "wpn_not_exists")
    assert response.status_code == 200
    results = response.json()
    assert results[0]["error"] == "Weapon not found"
    assert results[0]["recommendation"] is None


def test_update_matrix_planner_farming_locations(client):
    """刷取地点筛选通过 API 更新并返回完整账号数据。"""
    locations = {
        "world_energy_point_group01": True,
        "world_energy_point_group02": False,
    }
    response = client.post(
        "/api/profiles/matrix_planner_farming_locations",
        json={"locations": locations},
    )
    assert response.status_code == 200
    assert response.json()["matrix_planner_farming_locations"] == locations


def test_update_matrix_planner_farming_locations_empty_body(client):
    """空请求体默认为空筛选配置，不报错。"""
    response = client.post("/api/profiles/matrix_planner_farming_locations", json={})
    assert response.status_code == 200
    assert response.json()["matrix_planner_farming_locations"] == {}
