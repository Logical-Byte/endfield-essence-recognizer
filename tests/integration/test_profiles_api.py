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


def test_update_treasure_matrix_targets_named_profile(client):
    """导入落盘路径：带 profile_name 时写入目标账号且不切换激活账号。"""
    client.post("/api/profiles/switch", json={"name": "imported"})
    client.post("/api/profiles/switch", json={"name": "default"})

    response = client.post(
        "/api/profiles/treasure_matrix",
        json={
            "profile_name": "imported",
            "entries": [
                {
                    "weapon_id": "wpn_001",
                    "weapon_name": "W1",
                    "affix1_level": 4,
                    "affix2_level": 2,
                    "affix3_level": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "imported"
    # 断言条目真的写进去了：只查账号名的话，路由把 entries 丢掉也能过
    assert body["treasure_matrix"] == [
        {
            "weapon_id": "wpn_001",
            "weapon_name": "W1",
            "affix1_level": 4,
            "affix2_level": 2,
            "affix3_level": 1,
            "include_in_calculation": True,
            "priority": 0,
        }
    ]
    stored = client.get("/api/profiles").json()["profiles"]["imported"]
    assert [
        (entry["weapon_id"], entry["affix1_level"])
        for entry in stored["treasure_matrix"]
    ] == [("wpn_001", 4)]
    # 激活账号既没被切换，也没被写入
    active = client.get("/api/profiles/active").json()
    assert active["name"] == "default"
    assert active["treasure_matrix"] == []


def test_update_treasure_matrix_unknown_profile_returns_400(client):
    """目标账号不存在时返回 400，而不是把数据写进当前账号。"""
    response = client.post(
        "/api/profiles/treasure_matrix",
        json={"profile_name": "ghost", "entries": []},
    )

    assert response.status_code == 400
    assert client.get("/api/profiles/active").json()["name"] == "default"


def test_create_profile_does_not_switch_active(client):
    """新建账号接口只建不切，激活账号保持不变。"""
    response = client.post("/api/profiles/create", json={"name": "backup"})

    assert response.status_code == 200
    assert response.json()["name"] == "backup"
    assert client.get("/api/profiles/active").json()["name"] == "default"
    assert "backup" in client.get("/api/profiles").json()["profiles"]


def test_create_duplicate_profile_returns_400(client):
    """重复新建同名账号返回 400。"""
    first = client.post("/api/profiles/create", json={"name": "backup"})
    # 先确认第一次真的建成了：否则「接口对所有请求都返回 400」也能让下面通过
    assert first.status_code == 200

    response = client.post("/api/profiles/create", json={"name": "backup"})

    assert response.status_code == 400
