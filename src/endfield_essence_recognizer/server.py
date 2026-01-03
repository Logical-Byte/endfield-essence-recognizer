import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter, Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer import on_bracket_right, supported_window_titles
from endfield_essence_recognizer.data import Weapons, weapons
from endfield_essence_recognizer.log import LOGGING_CONFIG, logger, websocket_handler

# 加载 .env 文件
load_dotenv()

# 从环境变量读取配置
is_dev = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
api_host = os.getenv("API_HOST", "127.0.0.1")
api_port = int(os.getenv("API_PORT", "8000"))
dev_url = os.getenv("DEV_URL", "http://localhost:3000")
prod_url = f"http://{api_host}:{api_port}"
webview_url = dev_url if is_dev else prod_url


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
    global task
    task = asyncio.create_task(broadcast_logs())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


router = APIRouter(lifespan=lifespan)
websocket_connections: set[WebSocket] = set()
task: asyncio.Task | None = None
connection_event = asyncio.Event()


@router.get("/api/weapons")
async def get_weapons() -> Weapons:
    return weapons


@router.get("/api/config")
async def get_config() -> dict[str, Any]:
    from endfield_essence_recognizer.config import config

    return config.model_dump()


@router.post("/api/config")
async def post_config(new_config: dict[str, Any] = Body()) -> dict[str, Any]:
    from endfield_essence_recognizer.config import config

    config.update_from_dict(new_config)
    config.save()
    return config.model_dump()


@router.get("/api/screenshot")
async def get_screenshot(
    width: int = 1920,
    height: int = 1080,
    format: Literal["jpg", "jpeg", "png", "webp"] = "jpg",  # noqa: A002
    quality: int = 75,
):
    import base64

    import cv2
    import numpy as np

    from endfield_essence_recognizer.window import (
        get_active_support_window,
        screenshot_window,
    )

    window = get_active_support_window(supported_window_titles)
    if window is None:
        image = np.zeros((height, width, 3), dtype=np.uint8)
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

    _, encoded_bytes = cv2.imencode(ext, image, encode_param)

    # 返回 base64 编码的字符串
    base64_string = base64.b64encode(encoded_bytes.tobytes()).decode("utf-8")

    return f"data:{mime_type};base64,{base64_string}"


@router.post("/api/start_scanning")
async def start_scanning():
    on_bracket_right()


@router.websocket("/ws/logs")
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


app = FastAPI()

app.add_middleware(
    CORSMiddleware,  # ty:ignore[invalid-argument-type]
    allow_origins=["*"],  # 生产环境可指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
app.include_router(router)

if not is_dev:
    # 挂载静态文件目录（生产环境）
    DIST_DIR = Path("frontend-vuetify/dist")
    if DIST_DIR.exists():
        app.mount(
            "/",
            StaticFiles(directory=DIST_DIR, html=True),
        )
    else:
        logger.error("未找到前端构建文件夹，请先执行前端构建！")


config = uvicorn.Config(
    app=app, host=api_host, port=api_port, log_config=LOGGING_CONFIG
)
server = uvicorn.Server(config)
