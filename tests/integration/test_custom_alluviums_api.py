"""custom_alluviums API 集成测试。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.dependencies import get_custom_alluviums_path_dep
from endfield_essence_recognizer.server import app


@pytest.fixture
def data_file(tmp_path):
    """临时数据文件路径，避免测试改写开发者本机的自定义淤积点。"""
    return tmp_path / "custom_alluviums.json"


@pytest.fixture
def client(data_file):
    """替换数据文件依赖的 TestClient。

    这些接口不依赖启动期状态（管理器按请求构造），因此不进 lifespan：
    重复执行 lifespan 会把全局服务的事件队列绑到另一个事件循环上，
    破坏 test_lifespan 的断言。
    """

    def override_get_custom_alluviums_path():
        return data_file

    app.dependency_overrides[get_custom_alluviums_path_dep] = (
        override_get_custom_alluviums_path
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(name: str = "新版本淤积点") -> dict:
    """构造一条自定义淤积点的请求体。"""
    return {
        "name": name,
        "attribute_stats": [
            "gat_passive_attr_agi",
            "gat_passive_attr_main",
            "gat_passive_attr_atk",
        ],
        "secondary_stats": ["gat_passive_attr_atk"],
        "skill_stats": ["gst_passive_force"],
    }


def test_list_returns_empty_when_file_missing(client, data_file):
    """没有数据文件时返回空列表。"""
    response = client.get("/api/custom_alluviums")

    assert response.status_code == 200
    assert response.json() == []
    assert not data_file.exists()


def test_save_assigns_id_and_list_returns_it(client, data_file):
    """保存后能从列表接口读回，且数据已落盘。"""
    response = client.post("/api/custom_alluviums", json=_payload())

    assert response.status_code == 200
    saved = response.json()
    assert len(saved) == 1
    assert saved[0]["id"]
    assert saved[0]["name"] == "新版本淤积点"

    listed = client.get("/api/custom_alluviums").json()
    assert listed == saved

    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk[0]["id"] == saved[0]["id"]


def test_save_with_existing_id_updates_entry(client):
    """带既有 ID 保存是覆盖，不会新增条目。"""
    created = client.post("/api/custom_alluviums", json=_payload()).json()
    target_id = created[0]["id"]

    updated = client.post(
        "/api/custom_alluviums",
        json={
            "id": target_id,
            "name": "改名后",
            "attribute_stats": created[0]["attribute_stats"],
            "secondary_stats": created[0]["secondary_stats"],
            "skill_stats": ["gst_passive_heal"],
        },
    ).json()

    assert len(updated) == 1
    assert updated[0]["id"] == target_id
    assert updated[0]["name"] == "改名后"
    assert updated[0]["skill_stats"] == ["gst_passive_heal"]


def test_save_without_name_returns_400(client):
    """名称为空时明确报错，而不是写入一条无法辨认的条目。"""
    response = client.post("/api/custom_alluviums", json={**_payload(), "name": "  "})

    assert response.status_code == 400
    assert "名称" in response.json()["detail"]


def test_delete_removes_entry(client):
    """按稳定 ID 删除，返回剩余列表。"""
    created = client.post("/api/custom_alluviums", json=_payload("甲")).json()
    created = client.post("/api/custom_alluviums", json=_payload("乙")).json()
    assert len(created) == 2

    response = client.post(
        "/api/custom_alluviums/delete", json={"id": created[0]["id"]}
    )

    assert response.status_code == 200
    remaining = response.json()
    assert [item["name"] for item in remaining] == ["乙"]
    assert [item["name"] for item in client.get("/api/custom_alluviums").json()] == [
        "乙"
    ]


def test_delete_unknown_id_keeps_entries(client):
    """删除不存在的 ID 是幂等的，不影响已有条目。"""
    client.post("/api/custom_alluviums", json=_payload())

    response = client.post("/api/custom_alluviums/delete", json={"id": "不存在"})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_read_error_returns_500_instead_of_empty_list(client, data_file, monkeypatch):
    """文件读不出来时明确报错，不能让前端把它当成「没有自定义地点」。"""
    client.post("/api/custom_alluviums", json=_payload())

    def _deny_read(self: Path, **_kwargs: object) -> str:
        raise PermissionError("文件被占用")

    with monkeypatch.context() as patched:
        patched.setattr(Path, "read_text", _deny_read)

        response = client.get("/api/custom_alluviums")

    assert response.status_code == 500
    assert "读取" in response.json()["detail"]
