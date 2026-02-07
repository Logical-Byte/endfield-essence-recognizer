import asyncio
import importlib.resources
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Body, Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.core.layout import ResolutionProfile
from endfield_essence_recognizer.core.path import get_logs_dir
from endfield_essence_recognizer.core.scanner.engine import (
    ScannerEngine,
)
from endfield_essence_recognizer.deps import (
    default_user_setting_manager,
    get_log_service,
    get_resolution_profile,
    get_scanner_engine_dep,
    get_scanner_service,
    get_screenshot_service,
    get_screenshots_dir_dep,
    get_user_setting_manager_dep,
)
from endfield_essence_recognizer.hotkey_entrypoints import bind_hotkeys
from endfield_essence_recognizer.models.screenshot import (
    ImageFormat,
    ScreenshotRequest,
    ScreenshotResponse,
)
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)
from endfield_essence_recognizer.utils.log import (
    LOGGING_CONFIG,
    logger,
)
from endfield_essence_recognizer.version import __version__


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
        with bind_hotkeys(server_config):
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
    format: ImageFormat = ImageFormat.JPG,  # noqa: A002
    quality: int = 75,
    screenshot_service: ScreenshotService = Depends(get_screenshot_service),
) -> str | None:
    try:
        return await screenshot_service.capture_as_data_uri(
            width=width, height=height, format=format, quality=quality
        )
    except Exception as e:
        logger.exception(f"Failed to capture screenshot: {e}")
        return None


@app.post(
    "/api/take_and_save_screenshot",
    description="后端截图并保存到本地，返回文件路径和文件名",
)
async def take_and_save_screenshot(
    request: ScreenshotRequest,
    screenshot_dir: Path = Depends(get_screenshots_dir_dep),
    resolution_profile: ResolutionProfile = Depends(get_resolution_profile),
    screenshot_service: ScreenshotService = Depends(get_screenshot_service),
) -> ScreenshotResponse:
    """Takes a screenshot and saves it to a local directory."""
    try:
        full_path, file_name = await screenshot_service.capture_and_save(
            screenshot_dir=screenshot_dir,
            resolution_profile=resolution_profile,
            should_focus=request.should_focus,
            post_process=request.post_process,
            title=request.title,
            fmt=request.format,
        )
        return ScreenshotResponse(
            success=True,
            message="Screenshot saved successfully.",
            file_path=full_path,
            file_name=file_name,
        )
    except Exception as e:
        logger.exception(f"Failed to take and save screenshot: {e}")
        return ScreenshotResponse(
            success=False,
            message=str(e),
            file_path=None,
            file_name=None,
        )


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
