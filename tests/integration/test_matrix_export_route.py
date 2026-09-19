"""宝藏基质导出接口的图片 base64 体积上限回归测试。

覆盖两点：
1. schema 层：`image_base64` 声明了长度上限，边界内通过、超限抛 ValidationError；
2. 路由层：超限请求在校验阶段就被拒（4xx），不会落盘、也不会打开导出目录。

本文件只有一处 HTTP POST，且其载荷严格大于 MAX_IMAGE_BASE64_CHARS；
边界内的用例一律走 `TreasureMatrixExportRequest.model_validate`。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from endfield_essence_recognizer.api.routes import matrix_export
from endfield_essence_recognizer.api.routes.profiles import get_profile_manager
from endfield_essence_recognizer.dependencies import get_exports_dir_dep
from endfield_essence_recognizer.schemas.matrix_export import (
    MAX_IMAGE_BASE64_CHARS,
    TreasureMatrixExportRequest,
)

if TYPE_CHECKING:
    from pathlib import Path

# 路径由 api/router.py 的 prefix="/api"、matrix_export.router 的 prefix="/export"
# 以及路由装饰器 "/treasure_matrix" 组合而成。
_EXPORT_PATH = "/api/export/treasure_matrix"


def _oversize_image_base64() -> str:
    """返回比上限多一个字符的 base64 载荷。"""
    return "a" * (MAX_IMAGE_BASE64_CHARS + 1)


class _ProfileManagerRecorder:
    """记录路由体是否真的去取过当前账号名（只应在落盘路径上被调用）。"""

    def __init__(self) -> None:
        self.get_active_profile_name_calls = 0

    def get_active_profile_name(self) -> str:
        self.get_active_profile_name_calls += 1
        return "tester"


def test_treasure_matrix_export_request_accepts_image_base64_at_max_length() -> None:
    """边界内（正好等于上限）应当通过校验。"""
    request = TreasureMatrixExportRequest.model_validate(
        {"image_base64": "a" * MAX_IMAGE_BASE64_CHARS, "open_folder": False}
    )

    assert len(request.image_base64) == MAX_IMAGE_BASE64_CHARS


def test_treasure_matrix_export_request_rejects_image_base64_over_max_length() -> None:
    """超过上限一个字符即应被 pydantic 拒绝；这是本补丁的直接反证点。"""
    with pytest.raises(pydantic.ValidationError) as exc_info:
        TreasureMatrixExportRequest.model_validate(
            {"image_base64": _oversize_image_base64(), "open_folder": False}
        )

    errors = exc_info.value.errors()
    assert errors[0]["loc"] == ("image_base64",)
    assert errors[0]["type"] == "string_too_long"


def test_image_base64_field_declares_max_length_metadata() -> None:
    """把反证目标钉在 Field(max_length=...) 本身上。"""
    metadata = TreasureMatrixExportRequest.model_fields["image_base64"].metadata
    max_lengths = [item.max_length for item in metadata if hasattr(item, "max_length")]

    assert max_lengths == [MAX_IMAGE_BASE64_CHARS]


def test_oversize_image_base64_rejected_before_route_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """超限请求必须返回 4xx，并且没有文件落到导出目录、没有打开文件夹。"""
    app = FastAPI()
    api_router = APIRouter(prefix="/api")
    api_router.include_router(matrix_export.router)
    app.include_router(api_router)

    profile_manager = _ProfileManagerRecorder()
    app.dependency_overrides[get_exports_dir_dep] = lambda: tmp_path
    app.dependency_overrides[get_profile_manager] = lambda: profile_manager

    opened: list[Path] = []

    async def _record_open(directory: Path) -> None:
        opened.append(directory)

    monkeypatch.setattr(matrix_export, "_open_directory", _record_open)

    response = TestClient(app).post(
        _EXPORT_PATH,
        json={"image_base64": _oversize_image_base64(), "open_folder": False},
    )

    assert 400 <= response.status_code < 500, response.text
    assert opened == []
    assert profile_manager.get_active_profile_name_calls == 0
    assert list(tmp_path.iterdir()) == []
