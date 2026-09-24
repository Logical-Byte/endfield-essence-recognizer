import importlib.resources
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from endfield_essence_recognizer.api.routes.profiles import set_profile_manager
from endfield_essence_recognizer.core.config import ServerConfig, get_server_config
from endfield_essence_recognizer.core.path import get_root_dir
from endfield_essence_recognizer.dependencies import (
    default_user_setting_manager,
    get_event_service,
    get_log_service,
    get_static_game_data,
)
from endfield_essence_recognizer.hotkey_entrypoints import bind_hotkeys
from endfield_essence_recognizer.services.profile_manager import ProfileManager
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__


def log_welcome_message():
    """Log a formatted welcome and usage guide message to the logger."""
    message = f"""
==================================================
<green><bold>终末地基质妙妙小工具 v{__version__ or "?"} 已启动</></>
==================================================
<green><bold>使用前阅读：</></>
  - 请使用<yellow><bold>管理员权限</></>运行本工具，否则无法捕获全局热键
  - 支持分辨率自动缩放，按照原生 1080p 比例自动计算ROI缩放
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
    """Load user settings at startup."""
    user_setting_manager = default_user_setting_manager()
    user_setting_manager.load_user_setting()


def init_load_profiles():
    """在启动时加载账号配置。"""
    profiles_file = get_root_dir() / "profiles.json"
    profile_manager = ProfileManager(profiles_file)
    profile_manager.load()
    # 必须在用户配置加载之后执行：迁移依赖配置中自定义基质的顺序来解析旧下标。
    profile_manager.migrate_custom_stat_ids(
        default_user_setting_manager().get_custom_stat_ids()
    )
    # 武器数据随游戏版本更新后，个别武器的 ID 可能变化（如中文 ID 规范为
    # wpn_xxx）：按名称把失效引用改写为最新 ID，避免幽灵条目与重复条目。
    # 静态数据缺失/损坏时跳过迁移，迁移失败不应阻断服务启动。
    try:
        static_data = get_static_game_data()
        weapons_by_name = {
            weapon.name: weapon.weapon_id for weapon in static_data.list_weapons()
        }
        profile_manager.migrate_stale_weapon_ids(weapons_by_name)
    except Exception as exc:
        logger.warning(f"静态数据不可用，跳过武器 ID 迁移: {exc}")
    set_profile_manager(profile_manager)


def init_mount_frontend_build(app: FastAPI, server_config: ServerConfig):
    """挂载前端构建目录以提供静态文件服务。"""
    if server_config.dev_mode:
        return

    # 确保正确的 MIME 类型映射，避免 Windows 系统上的问题
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("application/javascript", ".mjs")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("application/json", ".json")
    mimetypes.add_type("application/json", ".map")
    mimetypes.add_type("image/svg+xml", ".svg")
    mimetypes.add_type("image/webp", ".webp")
    mimetypes.add_type("application/xml", ".xml")
    mimetypes.add_type("application/wasm", ".wasm")
    mimetypes.add_type("font/woff2", ".woff2")
    mimetypes.add_type("font/woff", ".woff")
    mimetypes.add_type("font/ttf", ".ttf")

    if not server_config.dist_dir:
        dist_dir = (
            Path(str(importlib.resources.files("endfield_essence_recognizer")))
            / "webui_dist"
        )
    else:
        dist_dir = Path(server_config.dist_dir)
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="dist")
    else:
        logger.error("未找到前端构建文件夹，请先执行前端构建！")


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_config = get_server_config()
    async with get_log_service().scope(server_config):
        async with get_event_service().scope():
            logger.success(f"Server configuration: {server_config.model_dump()}")
            init_mount_frontend_build(app, server_config)
            init_load_user_setting()
            init_load_profiles()
            log_welcome_message()
            with bind_hotkeys(server_config):
                yield
