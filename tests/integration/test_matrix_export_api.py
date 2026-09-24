import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_exports_dir_dep
from endfield_essence_recognizer.server import app

# 1x1 透明 PNG，仅用于验证落盘链路
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)

# 1x1 无损 WebP。前端主路径产出的就是 WebP，PNG 只是不支持时的回退。
WEBP_BASE64 = "UklGRh4AAABXRUJQVlA4TBEAAAAvAAAAAAfQ//73v/+BiOh/AAA="


@pytest.fixture
def mock_profile_manager():
    manager = MagicMock()
    manager.get_active_profile_name.return_value = "default"
    return manager


@pytest.fixture
def client(mock_profile_manager, tmp_path):
    app.dependency_overrides[get_exports_dir_dep] = lambda: tmp_path / "exports"
    app.dependency_overrides[get_profile_manager] = lambda: mock_profile_manager

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_open_directory():
    """拦截打开文件夹，避免测试时真的弹出资源管理器。"""
    with patch(
        "endfield_essence_recognizer.api.routes.matrix_export._open_directory"
    ) as mock:
        yield mock


def test_export_saves_webp(client, mock_open_directory, tmp_path):
    """WebP 是前端主路径，应落盘为 .webp 而不是被当成 PNG。"""
    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": WEBP_BASE64, "open_folder": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_name"].startswith("default_")
    assert data["file_name"].endswith(".webp")

    saved = tmp_path / "exports" / data["file_name"]
    assert saved.exists()
    assert saved.read_bytes() == base64.b64decode(WEBP_BASE64)


def test_export_saves_png(client, mock_open_directory, tmp_path):
    """PNG 是浏览器不支持 WebP 编码时的回退通道，同样要能落盘。"""
    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": PNG_BASE64, "open_folder": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_name"].startswith("default_")
    assert data["file_name"].endswith(".png")

    saved = tmp_path / "exports" / data["file_name"]
    assert saved.exists()
    assert saved.read_bytes() == base64.b64decode(PNG_BASE64)


def test_export_rejects_unsupported_format(client, mock_open_directory):
    """既不是 WebP 也不是 PNG 的内容必须被拒绝，这个接口不做通用文件落盘。"""
    response = client.post(
        "/api/export/treasure_matrix",
        json={
            "image_base64": base64.b64encode(b"not an image at all").decode(),
            "open_folder": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "WebP" in data["message"]
    assert "PNG" in data["message"]
    assert data["file_path"] is None


def test_export_rejects_invalid_base64(client, mock_open_directory):
    """非法 base64 应报错而不是抛出未捕获异常。"""
    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": "!!!not base64!!!", "open_folder": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "base64" in data["message"]


def test_export_sanitizes_profile_name(
    client, mock_open_directory, mock_profile_manager, tmp_path
):
    """账号名里的路径分隔符与非法字符必须被清洗，不能写到导出目录之外。"""
    mock_profile_manager.get_active_profile_name.return_value = "../../evil:name?"

    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": PNG_BASE64, "open_folder": False},
    )

    data = response.json()
    assert data["success"] is True
    assert "/" not in data["file_name"]
    assert "\\" not in data["file_name"]
    assert ":" not in data["file_name"]
    assert (tmp_path / "exports" / data["file_name"]).exists()


def test_export_skips_open_folder_when_disabled(client, mock_open_directory):
    """open_folder=false 时不应触发打开文件夹。"""
    client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": PNG_BASE64, "open_folder": False},
    )

    mock_open_directory.assert_not_called()


def test_export_opens_folder_when_enabled(client, mock_open_directory):
    """open_folder=true 时应触发打开文件夹。"""
    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": PNG_BASE64, "open_folder": True},
    )

    assert response.json()["success"] is True
    mock_open_directory.assert_called_once()


def test_export_survives_open_folder_failure(client, mock_open_directory, tmp_path):
    """打开文件夹失败不能把已经落盘成功的导出判为失败。"""
    mock_open_directory.side_effect = OSError("explorer 挂了")

    response = client.post(
        "/api/export/treasure_matrix",
        json={"image_base64": PNG_BASE64, "open_folder": True},
    )

    data = response.json()
    assert data["success"] is True
    assert "打开文件夹失败" in data["message"]
    assert (tmp_path / "exports" / data["file_name"]).exists()
