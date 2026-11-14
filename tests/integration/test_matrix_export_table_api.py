"""宝藏基质表格导出接口（CSV / JSON）的落盘回归测试。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from fastapi.testclient import TestClient

from endfield_essence_recognizer.api.routes import matrix_export
from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_exports_dir_dep
from endfield_essence_recognizer.schemas.matrix_export import (
    MAX_TABLE_CONTENT_CHARS,
    TreasureMatrixTableExportRequest,
)
from endfield_essence_recognizer.server import app

_TABLE_EXPORT_PATH = "/api/export/treasure_matrix/table"

# 带 CRLF 与中文的 CSV，用于验证行尾不被二次转换、中文不被转义
CSV_CONTENT = "武器ID,名称\r\nwpn_funnel_0009,领航者\r\n"

JSON_CONTENT = '{\n  "count": 0,\n  "items": []\n}\n'


class _FrozenDatetime(datetime):
    """时间戳固定在同一秒，用来稳定复现「同秒两次导出」。"""

    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return cls(2026, 2, 6, 12, 0, 0)


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


def _post_table(
    client: TestClient,
    file_format: str,
    content: str,
    open_folder: bool = False,
    file_stem: str | None = None,
):
    body: dict[str, object] = {
        "format": file_format,
        "content": content,
        "open_folder": open_folder,
    }
    if file_stem is not None:
        body["file_stem"] = file_stem
    return client.post(_TABLE_EXPORT_PATH, json=body)


def test_export_csv_writes_bom_and_keeps_crlf(client, mock_open_directory, tmp_path):
    """CSV 必须带 UTF-8 BOM（Excel 才认），且 CRLF 不能被文本模式翻成 CRCRLF。"""
    response = _post_table(client, "csv", CSV_CONTENT)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["file_name"].startswith("default_")
    assert data["file_name"].endswith(".csv")

    saved = tmp_path / "exports" / data["file_name"]
    raw = saved.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\r\n" not in raw
    assert raw.decode("utf-8") == f"\ufeff{CSV_CONTENT}"


def test_export_json_writes_plain_utf8(client, mock_open_directory, tmp_path):
    """JSON 不加 BOM，否则严格解析器会把 BOM 当成非法字符。"""
    response = _post_table(client, "json", JSON_CONTENT)

    data = response.json()
    assert data["success"] is True
    assert data["file_name"].endswith(".json")

    saved = tmp_path / "exports" / data["file_name"]
    assert saved.read_bytes() == JSON_CONTENT.encode()
    assert saved.read_text(encoding="utf-8") == JSON_CONTENT


def test_export_rejects_unknown_format(client, mock_open_directory, tmp_path):
    """format 只接受 csv/json，其它值在校验阶段被拒，不落盘。"""
    response = _post_table(client, "exe", JSON_CONTENT)

    assert response.status_code == 422
    assert not (tmp_path / "exports").exists()


def test_export_rejects_content_over_max_length():
    """超长内容在校验阶段被拒；这是 16 MiB 上限的直接反证点。"""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        TreasureMatrixTableExportRequest.model_validate(
            {
                "format": "json",
                "content": "a" * (MAX_TABLE_CONTENT_CHARS + 1),
                "open_folder": False,
            }
        )

    errors = exc_info.value.errors()
    assert errors[0]["loc"] == ("content",)
    assert errors[0]["type"] == "string_too_long"


def test_export_sanitizes_profile_name(
    client, mock_open_directory, mock_profile_manager, tmp_path
):
    """账号名里的路径分隔符与非法字符必须被清洗，不能写到导出目录之外。"""
    mock_profile_manager.get_active_profile_name.return_value = "../../evil:name?"

    data = _post_table(client, "csv", CSV_CONTENT).json()

    assert data["success"] is True
    assert "/" not in data["file_name"]
    assert "\\" not in data["file_name"]
    assert ":" not in data["file_name"]
    assert (tmp_path / "exports" / data["file_name"]).exists()


def test_export_uses_custom_file_stem(
    client, mock_open_directory, mock_profile_manager, tmp_path
):
    """导入前快照要写目标账号名；指定主干时同样要走非法字符清洗。"""
    data = _post_table(
        client, "json", JSON_CONTENT, file_stem="账号A/..\\导入前备份"
    ).json()

    assert data["success"] is True
    assert data["file_name"].startswith("账号A_.._导入前备份_")
    assert "/" not in data["file_name"]
    assert "\\" not in data["file_name"]
    # 指定主干时就不该再用激活账号名
    mock_profile_manager.get_active_profile_name.assert_not_called()
    assert (tmp_path / "exports" / data["file_name"]).exists()


def test_repeated_export_same_second_does_not_overwrite(
    client, mock_open_directory, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """同一秒内连续导出两次必须落成两个文件。

    回归：时间戳只到秒，此前第二次导出会静默覆盖第一次——连点两次保存、
    或「导入前备份」与正常导出撞在同一秒时，用户会失去回滚依据。
    """
    monkeypatch.setattr(matrix_export, "datetime", _FrozenDatetime)

    first = _post_table(client, "json", JSON_CONTENT).json()
    second = _post_table(client, "json", JSON_CONTENT).json()

    assert first["success"] is True
    assert second["success"] is True
    assert first["file_name"] != second["file_name"]
    assert second["file_name"] == first["file_name"].replace(".json", "-2.json")
    assert (tmp_path / "exports" / first["file_name"]).exists()
    assert (tmp_path / "exports" / second["file_name"]).exists()


def test_export_skips_open_folder_when_disabled(client, mock_open_directory):
    """open_folder=false 时不应触发打开文件夹。"""
    _post_table(client, "csv", CSV_CONTENT)

    mock_open_directory.assert_not_called()


def test_export_opens_folder_when_enabled(client, mock_open_directory):
    """open_folder=true 时应触发打开文件夹。"""
    response = _post_table(client, "csv", CSV_CONTENT, open_folder=True)

    assert response.json()["success"] is True
    mock_open_directory.assert_called_once()


def test_export_survives_open_folder_failure(client, mock_open_directory, tmp_path):
    """打开文件夹失败不能把已经落盘成功的导出判为失败。"""
    mock_open_directory.side_effect = OSError("explorer 挂了")

    data = _post_table(client, "json", JSON_CONTENT, open_folder=True).json()

    assert data["success"] is True
    assert "打开文件夹失败" in data["message"]
    assert (tmp_path / "exports" / data["file_name"]).exists()
