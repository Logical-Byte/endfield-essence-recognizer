import asyncio
import os
import platform

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from endfield_essence_recognizer.core.path import get_logs_dir
from endfield_essence_recognizer.dependencies import get_system_service
from endfield_essence_recognizer.schemas.user_setting import (
    WINDOW_HEIGHT_MAX,
    WINDOW_HEIGHT_MIN,
    WINDOW_WIDTH_MAX,
    WINDOW_WIDTH_MIN,
)
from endfield_essence_recognizer.services.system_service import SystemService
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

router = APIRouter(prefix="", tags=["system"])


class WindowSizePayload(BaseModel):
    """调整窗口尺寸的请求体，单位为像素。"""

    width: int = Field(ge=WINDOW_WIDTH_MIN, le=WINDOW_WIDTH_MAX)
    height: int = Field(ge=WINDOW_HEIGHT_MIN, le=WINDOW_HEIGHT_MAX)


@router.get("/version")
async def get_version() -> str | None:
    return __version__


@router.post("/exit")
async def exit_app(
    system_service: SystemService = Depends(get_system_service),
) -> None:
    system_service.exit_application()


@router.post("/window/resize")
async def resize_window(
    payload: WindowSizePayload,
    system_service: SystemService = Depends(get_system_service),
) -> None:
    """立即把主窗口调整为指定尺寸，无需重启程序。"""
    system_service.resize_window(payload.width, payload.height)


@router.post("/open_logs_folder")
async def open_logs_folder() -> None:
    LOGS_DIR = get_logs_dir()

    try:
        if platform.system() == "Windows":  # Windows
            os.startfile(LOGS_DIR)
        elif platform.system() == "Darwin":  # macOS
            await asyncio.create_subprocess_exec("open", str(LOGS_DIR))
        else:  # Linux and others
            await asyncio.create_subprocess_exec("xdg-open", str(LOGS_DIR))
        logger.info(f"已打开日志目录：{LOGS_DIR}")
    except Exception as e:
        logger.exception(f"打开日志目录时出错：{e}")
        raise
