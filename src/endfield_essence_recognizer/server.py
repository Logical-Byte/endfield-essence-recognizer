import asyncio
import importlib.resources
import os
from contextlib import asynccontextmanager, contextmanager
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
from endfield_essence_recognizer.core.scanner.engine import (
    ScannerEngine,
    recognize_once,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.deps import (
    default_scanner_context,
    default_scanner_engine,
    default_user_setting_manager,
    get_audio_service,
    get_log_service,
    get_resolution_profile,
    get_scanner_engine_dep,
    get_scanner_service,
    get_user_setting_manager_dep,
    get_window_manager_dep,
    get_window_manager_singleton,
)
from endfield_essence_recognizer.models.screenshot import (
    ScreenshotRequest,
    ScreenshotResponse,
)
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)
from endfield_essence_recognizer.utils.log import (
    LOGGING_CONFIG,
    logger,
)
from endfield_essence_recognizer.version import __version__


def handle_keyboard_single_recognition():
    """处理 "[" 键按下事件 - 仅识别不操作"""
    window_manager: WindowManager = get_window_manager_singleton()
    scanner_ctx: ScannerContext = default_scanner_context()
    if not window_manager.target_is_active:
        logger.debug('终末地窗口不在前台，忽略 "[" 键。')
        return
    else:
        logger.info('检测到 "[" 键，开始识别基质')
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
        scanner = default_scanner_engine()
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


@contextmanager
def bind_hotkeys():
    """Context manager to bind and unbind global hotkeys."""
    keyboard.add_hotkey("[", handle_keyboard_single_recognition)
    keyboard.add_hotkey("]", handle_keyboard_auto_click)
    keyboard.add_hotkey("alt+delete", handle_keyboard_on_exit)
    logger.info("全局热键已注册")
    try:
        yield
    finally:
        keyboard.unhook_all()
        logger.info("全局热键已注销")


def log_welcome_message():
    """Log a formatted welcome and usage guide message to the logger."""
    message = """
==================================================
<green><bold>终末地基质妙妙小工具已启动</></>
==================================================
<green><bold>使用前阅读：</></>
  - 请使用<yellow><bold>管理员权限</></>运行本工具，否则无法捕获全局热键
  - 请在终末地的设置中将分辨率调整为 <yellow><bold>1920×1080 窗口</></>
  - 请按 "<green><bold>N</></>" 键打开终末地<yellow><bold>贵重品库</></>并切换到<yellow><bold>武器基质</></>页面
  - 在运行过程中，请确保终末地窗口<yellow><bold>置于前台</></>

<green><bold>功能介绍：</></>
  - 按 "<green><bold>[</></>" 键识别当前基质，仅识别不操作
  - 按 "<green><bold>]</></>" 键扫描所有基质，并根据设置，自动锁定或者解锁基质
    基质扫描过程中再次按 "<green><bold>]</></>" 键中断扫描
  - 按 "<green><bold>Alt+Delete</></>" 退出程序

  <cyan><bold>宝藏基质和养成材料：</></>可以在设置界面自定义。默认情况下，如果这个基质和任何一把武器能对上，则是宝藏，否则是养成材料。
==================================================
"""
    logger.opt(colors=True).info(message)


def init_load_user_setting():
    """
    Load user settings at startup.

    Side effects:
    - Loads settings into the UserSettingManager singleton, making them available for the rest of the application.
    - If the settings file does not exist or is invalid, it will be created and/or backed up.
    - Logs debug messages.
    """
    user_setting_manager = default_user_setting_manager()
    user_setting_manager.load_user_setting()


def init_mount_frontend_build(app: FastAPI, server_config: ServerConfig):
    """
    Mount the frontend build directory to serve static files.

    This should be called during the application startup phase, after loading user settings and before registering hotkeys.

    Args:
        app: The FastAPI application instance to mount the static files on.
        server_config: The server configuration specifying dev mode and the frontend
            distribution directory to mount.
    """
    if server_config.dev_mode:
        # dev mode uses Vite dev server, no need to mount static files
        return
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_config = get_server_config()
    async with get_log_service().scope(server_config):
        logger.success(f"Server configuration: {server_config.model_dump()}")
        init_mount_frontend_build(app, server_config)
        init_load_user_setting()
        log_welcome_message()
        with bind_hotkeys():
            yield


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


@app.post(
    "/api/take_and_save_screenshot",
    description="后端截图并保存到本地，返回文件路径和文件名",
)
async def take_and_save_screenshot(
    request: ScreenshotRequest,
) -> ScreenshotResponse:
    """Takes a screenshot and saves it to a local directory."""
    # TODO: Implementation
    _ = request
    dummy_response = ScreenshotResponse(
        success=True,
        message="截图成功",
        file_path="C:/dummy/path/Endfield_screenshot.png",
        file_name="Endfield_screenshot.png",
    )
    return dummy_response


@app.get("/api/version")
async def get_version() -> str | None:
    return __version__


@app.post("/api/start_scanning")
async def start_scanning(
    scanner: ScannerEngine = Depends(get_scanner_engine_dep),
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
async def websocket_logs(
    websocket: WebSocket,
    log_service: LogService = Depends(get_log_service),
):
    await websocket.accept()
    await log_service.add_connection(websocket)
    logger.info("WebSocket 日志连接已建立。")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket 日志连接已断开。")
    except Exception as e:
        logger.exception(f"WebSocket 日志连接出错：{e}")
    finally:
        log_service.remove_connection(websocket)


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
