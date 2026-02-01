import asyncio
import importlib.resources
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import uvicorn
from fastapi import Body, Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer import supported_window_titles, toggle_scan
from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.core.path import get_logs_dir
from endfield_essence_recognizer.deps import get_user_setting_manager
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)
from endfield_essence_recognizer.utils.log import (
    LOGGING_CONFIG,
    logger,
    websocket_handler,
)
from endfield_essence_recognizer.version import __version__


async def broadcast_logs():
    """异步任务，持续监听日志队列并广播日志消息"""
    await connection_event.wait()
    while True:
        message = await websocket_handler.log_queue.get()
        disconnected_connections = set()
        for connection in websocket_connections.copy():  # 防止在迭代时修改集合
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                disconnected_connections.add(connection)
            except Exception as e:
                logger.exception(f"发送日志到 WebSocket 连接时出错：{e}")
                disconnected_connections.add(connection)
        for dc in disconnected_connections:
            websocket_connections.discard(dc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_config = get_server_config()
    logger.success(f"Server configuration: {server_config.model_dump()}")

    if not server_config.dev_mode:
        if not server_config.dist_dir:
            # use the default shipped build directory
            dist_dir = (
                Path(importlib.resources.files("endfield_essence_recognizer"))
                / "webui_dist"
            )
        else:
            # use the specified directory
            dist_dir = Path(server_config.dist_dir)
        # 挂载静态文件目录（生产环境）
        if dist_dir.exists():
            app.mount(
                "/",
                StaticFiles(directory=dist_dir, html=True),
                name="dist",
            )
        else:
            logger.error("未找到前端构建文件夹，请先执行前端构建！")

    global task
    task = asyncio.create_task(broadcast_logs())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


websocket_connections: set[WebSocket] = set()
task: asyncio.Task | None = None
connection_event = asyncio.Event()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,  # ty:ignore[invalid-argument-type]
    allow_origins=["*"],  # 生产环境可指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
async def get_config(
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager),
) -> dict[str, Any]:
    return user_setting_manager.get_user_setting_ref().model_dump()


@app.post("/api/config")
async def post_config(
    new_config: dict[str, Any] = Body(),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager),
) -> dict[str, Any]:
    # from endfield_essence_recognizer.models.user_setting import config

    # config.update_from_dict(new_config)
    # config.save()
    # return config.model_dump()
    user_setting_manager.update_from_dict(new_config)
    return user_setting_manager.get_user_setting_ref().model_dump()


@app.get("/api/screenshot")
async def get_screenshot(
    width: int = 1920,
    height: int = 1080,
    format: Literal["jpg", "jpeg", "png", "webp"] = "jpg",  # noqa: A002
    quality: int = 75,
) -> str | None:
    import base64

    import cv2

    from endfield_essence_recognizer.utils.window import (
        get_active_support_window,
        screenshot_window,
    )

    window = get_active_support_window(supported_window_titles)
    if window is None:
        return None
    else:
        image = screenshot_window(window)
        image = cv2.resize(image, (width, height))
        logger.success("成功截取终末地窗口截图。")

    if format.lower() == "png":
        encode_param = [
            # cv2.IMWRITE_PNG_COMPRESSION,
            # min(9, max(0, quality // 10)),
        ]  # PNG compression 0-9
        ext = ".png"
        mime_type = "image/png"
    elif format.lower() == "webp":
        encode_param = [cv2.IMWRITE_WEBP_QUALITY, min(100, max(0, quality))]
        ext = ".webp"
        mime_type = "image/webp"
    elif format.lower() == "jpg" or format.lower() == "jpeg":
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, min(100, max(0, quality))]
        ext = ".jpg"
        mime_type = "image/jpeg"
    else:
        return None

    _, encoded_bytes = cv2.imencode(ext, image, encode_param)

    # 返回 base64 编码的字符串
    base64_string = base64.b64encode(encoded_bytes.tobytes()).decode("utf-8")

    return f"data:{mime_type};base64,{base64_string}"


@app.get("/api/version")
async def get_version() -> str | None:
    return __version__


@app.post("/api/start_scanning")
async def start_scanning() -> None:
    toggle_scan()


@app.post("/api/open_logs_folder")
async def open_logs_folder() -> None:
    import platform

    from endfield_essence_recognizer.utils.log import logger

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


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    websocket_connections.add(websocket)
    connection_event.set()
    logger.info("WebSocket 日志连接已建立。")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)
        logger.info("WebSocket 日志连接已断开。")
    except Exception as e:
        logger.exception(f"WebSocket 日志连接出错：{e}")


app.mount(
    "/api/data",
    StaticFiles(
        directory=str(importlib.resources.files("endfield_essence_recognizer") / "data")
    ),
    name="data",
)


def get_server() -> uvicorn.Server:
    cfg: ServerConfig = get_server_config()
    api_host = cfg.api_host
    api_port = cfg.api_port
    config = uvicorn.Config(
        app=app, host=api_host, port=api_port, log_config=LOGGING_CONFIG
    )
    server = uvicorn.Server(config)
    return server
