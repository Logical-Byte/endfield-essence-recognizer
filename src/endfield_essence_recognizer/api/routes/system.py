import asyncio
import os
import platform

from fastapi import APIRouter

from endfield_essence_recognizer.core.path import get_logs_dir
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

router = APIRouter(prefix="", tags=["system"])


@router.get("/version")
async def get_version() -> str | None:
    return __version__


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
