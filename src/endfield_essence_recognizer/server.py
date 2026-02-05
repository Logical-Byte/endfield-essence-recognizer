import asyncio
import importlib.resources
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import keyboard
import uvicorn
from fastapi import Body, Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.core.path import get_logs_dir
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.deps import (
    default_essence_scanner,
    default_scanner_context,
    default_user_setting_manager,
    get_audio_service,
    get_essence_scanner_dep,
    get_resolution_profile,
    get_scanner_service,
    get_user_setting_manager_dep,
    get_window_manager_dep,
    get_window_manager_singleton,
)
from endfield_essence_recognizer.essence_scanner import EssenceScanner, recognize_once
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)
from endfield_essence_recognizer.utils.log import (
    LOGGING_CONFIG,
    logger,
    websocket_handler,
)
from endfield_essence_recognizer.version import __version__


def handle_keyboard_single_recognition():
    """处理 "[" 键按下事件 - 仅识别不操作"""
    window_manager: WindowManager = get_window_manager_singleton()
    scanner_ctx: ScannerContext = default_scanner_context()
    if not window_manager.target_is_active:
        logger.debug("终末地窗口不在前台，忽略 '[' 键。")
        return
    else:
        logger.info("检测到 '[' 键，开始识别基质")
        recognize_once(
            window_manager,
            scanner_ctx,
            default_user_setting_manager().get_user_setting(),
            get_resolution_profile(),
        )


def handle_keyboard_toggle_scan():
    """切换基质扫描状态"""
    scanner_service = get_scanner_service()
    audio_service = get_audio_service()

    if not scanner_service.is_running():
        logger.info("开始扫描基质")
        scanner = default_essence_scanner()
        scanner_service.start_scan(scanner_factory=lambda: scanner)
        audio_service.play_enable()
    else:
        logger.info("停止扫描基质")
        scanner_service.stop_scan()
        audio_service.play_disable()


def handle_keyboard_auto_click():
    """处理 "]" 键按下事件 - 切换自动点击"""
    window_manager: WindowManager = get_window_manager_singleton()

    if not window_manager.target_is_active:
        logger.debug('终末地窗口不在前台，忽略 "]" 键。')
        return
    else:
        handle_keyboard_toggle_scan()


def handle_keyboard_on_exit():
    """处理 Alt+Delete 按下事件 - 退出程序"""
    logger.info('检测到 "Alt+Delete"，正在退出程序...')

    # 停止扫描器
    scanner_service = get_scanner_service()
    if scanner_service.is_running():
        scanner_service.stop_scan()

    # 关闭 webview 窗口，剩下的清理工作交给 main 函数
    from endfield_essence_recognizer.webui import window

    window.destroy()


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
    global connection_event
    connection_event = asyncio.Event()

    server_config = get_server_config()
    logger.success(f"Server configuration: {server_config.model_dump()}")

    if not server_config.dev_mode:
        if not server_config.dist_dir:
            # use the default shipped build directory
            dist_dir = (
                Path(str(importlib.resources.files("endfield_essence_recognizer")))
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

    # 注册热键
    keyboard.add_hotkey("[", handle_keyboard_single_recognition)
    keyboard.add_hotkey("]", handle_keyboard_auto_click)
    keyboard.add_hotkey("alt+delete", handle_keyboard_on_exit)
    logger.info("全局热键已注册")

    global task
    task = asyncio.create_task(broadcast_logs())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # 注销热键
    keyboard.unhook_all()
    logger.info("全局热键已注销")


websocket_connections: set[WebSocket] = set()
task: asyncio.Task | None = None
connection_event: asyncio.Event


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
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
) -> UserSetting:
    return user_setting_manager.get_user_setting_ref()


@app.post("/api/config")
async def post_config(
    new_config: UserSetting = Body(),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
) -> UserSetting:
    user_setting_manager.update_from_user_setting(new_config)
    return user_setting_manager.get_user_setting_ref()


@app.get("/api/screenshot")
async def get_screenshot(
    width: int = 1920,
    height: int = 1080,
    format: Literal["jpg", "jpeg", "png", "webp"] = "jpg",  # noqa: A002
    quality: int = 75,
    window_manager: WindowManager = Depends(get_window_manager_dep),
) -> str | None:
    import base64

    import cv2

    if not window_manager.target_is_active:
        return None
    else:
        image = window_manager.screenshot()
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
async def start_scanning(
    scanner: EssenceScanner = Depends(get_essence_scanner_dep),
    scanner_service: ScannerService = Depends(get_scanner_service),
) -> None:
    scanner_service.toggle_scan(scanner_factory=lambda: scanner)


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
