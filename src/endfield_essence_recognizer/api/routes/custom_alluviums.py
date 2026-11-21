"""自定义能量淤积点 API 路由。

自定义淤积点落盘在 `custom_alluviums.json`，与账号数据无关：
读取、保存、删除都是全局操作。
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from endfield_essence_recognizer.dependencies import get_custom_alluviums_path_dep
from endfield_essence_recognizer.schemas.custom_alluvium import CustomAlluvium
from endfield_essence_recognizer.services.custom_alluvium_manager import (
    CustomAlluviumManager,
    CustomAlluviumReadError,
)

router = APIRouter(prefix="/custom_alluviums", tags=["custom alluviums"])


@contextmanager
def _read_error_as_http() -> Iterator[None]:
    """把「文件读不出来」翻译成 500。

    读不到文件时不能返回空列表：前端会把空列表当成「没有自定义地点」，用户
    随后保存就会覆盖掉读不出来的内容。
    """
    try:
        yield
    except CustomAlluviumReadError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_custom_alluvium_manager(
    data_file: Path = Depends(get_custom_alluviums_path_dep),
) -> CustomAlluviumManager:
    """按请求构造管理器实例。

    管理器没有内存状态、读写的是几 KB 的小文件，因此不需要单例。
    """
    return CustomAlluviumManager(data_file)


@router.get("")
async def list_custom_alluviums(
    manager: CustomAlluviumManager = Depends(get_custom_alluvium_manager),
) -> list[CustomAlluvium]:
    """获取全部自定义淤积点。"""
    with _read_error_as_http():
        return manager.list_all()


@router.post("")
async def save_custom_alluvium(
    entry: CustomAlluvium,
    manager: CustomAlluviumManager = Depends(get_custom_alluvium_manager),
) -> list[CustomAlluvium]:
    """新增或按稳定 ID 覆盖一条自定义淤积点。

    `id` 为空表示新建，后端会分配稳定 ID；返回保存后的完整列表。
    """
    try:
        with _read_error_as_http():
            return manager.upsert(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class DeleteCustomAlluviumRequest(BaseModel):
    """删除自定义淤积点的请求体。"""

    id: str


@router.post("/delete")
async def delete_custom_alluvium(
    request: DeleteCustomAlluviumRequest,
    manager: CustomAlluviumManager = Depends(get_custom_alluvium_manager),
) -> list[CustomAlluvium]:
    """按稳定 ID 删除一条自定义淤积点，返回删除后的完整列表。"""
    with _read_error_as_http():
        return manager.delete(request.id)
