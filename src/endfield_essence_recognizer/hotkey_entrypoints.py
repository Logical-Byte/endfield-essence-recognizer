import asyncio
from contextlib import contextmanager
from functools import wraps

import keyboard

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.core.interfaces import HotkeyHandler
from endfield_essence_recognizer.core.scanner.context import ScannerContext
from endfield_essence_recognizer.core.scanner.engine import (
    recognize_once,
)
from endfield_essence_recognizer.core.window import WindowManager
from endfield_essence_recognizer.deps import (
    default_scanner_context,
    default_scanner_engine,
    default_user_setting_manager,
    get_audio_service,
    get_resolution_profile,
    get_scanner_service,
    get_screenshot_service,
    get_screenshots_dir_dep,
    get_webview_window_manager,
    get_window_manager_singleton,
)
from endfield_essence_recognizer.models.screenshot import (
    ScreenshotSaveFormat,
)
from endfield_essence_recognizer.utils.log import (
    logger,
)


def hotkey_handler(
    require_game_exists: bool = True,
    require_game_or_webview_active: bool = True,
):
    """
    Hotkey 触发时的装饰器，用于日志记录和窗口状态检查。

    Args:
        require_game_exists: 是否要求终末地游戏窗口存在。
        require_game_or_webview_active: 是否要求终末地游戏窗口或 WebView 窗口在前台。
    """

    def decorator(func: HotkeyHandler) -> HotkeyHandler:
        @wraps(func)
        def wrapper(key: str) -> None:
            logger.debug(f'检测到热键 "{key}" 被按下。')

            # 如果需要，检查游戏窗口是否存在
            if require_game_exists:
                if not check_game_window_exists():
                    return

            # 如果需要，检查游戏窗口或 WebView 窗口是否在前台
            if require_game_or_webview_active:
                if not check_game_or_webview_is_active():
                    return

            return func(key)

        return wrapper

    return decorator


def check_game_window_exists() -> bool:
    """
    检查终末地游戏窗口是否存在。

    Returns:
        bool: 如果游戏窗口存在则返回 True，否则返回 False。
    """
    window_manager: WindowManager = get_window_manager_singleton()
    if not window_manager.target_exists:
        logger.debug("未检测到终末地窗口，停止快捷键操作。")
        return False
    return True


def check_game_or_webview_is_active() -> bool:
    """
    检查终末地游戏窗口或 WebView 窗口是否在前台，打印相关日志。

    Returns:
        bool: 如果游戏窗口或 WebView 窗口在前台则返回 True，否则返回 False。
    """
    window_manager: WindowManager = get_window_manager_singleton()
    webview_window_manager: WindowManager = get_webview_window_manager()

    if window_manager.target_is_active:
        logger.debug("终末地窗口在前台，允许快捷键操作。")
        return True
    elif webview_window_manager.target_is_active:
        logger.debug("WebView 窗口在前台，允许快捷键操作。")
        return True
    else:
        logger.debug("前台窗口不是终末地或 WebView，停止快捷键操作。")
        return False


@hotkey_handler(
    require_game_exists=True,
    require_game_or_webview_active=True,
)
def handle_keyboard_single_recognition(key: str):
    """处理 "[" 键按下事件 - 仅识别不操作"""
    import time

    window_manager: WindowManager = get_window_manager_singleton()
    scanner_ctx: ScannerContext = default_scanner_context()
    if not window_manager.target_is_active:
        logger.debug(
            f'终末地窗口不在前台，尝试切换到前台以进行识别基质操作 "{key}" 键。'
        )
        if window_manager.activate():
            time.sleep(0.3)
        if window_manager.show():
            # make sure the window is visible
            time.sleep(0.3)

    logger.info(f'检测到 "{key}" 键，开始识别基质')
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


@hotkey_handler(
    require_game_exists=True,
    require_game_or_webview_active=True,
)
def handle_keyboard_auto_click(key: str):
    """处理 "]" 键按下事件 - 切换自动点击"""
    window_manager: WindowManager = get_window_manager_singleton()

    if not window_manager.target_is_active:
        logger.debug(f'终末地窗口不在前台，忽略 "{key}" 键。')
        return
    else:
        logger.info(f'检测到 "{key}" 键，切换自动点击状态')
        handle_keyboard_toggle_scan()


@hotkey_handler(require_game_exists=False, require_game_or_webview_active=False)
def handle_keyboard_on_exit(key: str):
    """处理 Alt+Delete 按下事件 - 退出程序"""
    logger.info(f'检测到 "{key}"，正在退出程序...')

    # 停止扫描器
    scanner_service = get_scanner_service()
    if scanner_service.is_running():
        scanner_service.stop_scan()

    # 关闭 webview 窗口，剩下的清理工作交给 main 函数
    from endfield_essence_recognizer.webui import window

    window.destroy()


@hotkey_handler(
    require_game_exists=True,
    require_game_or_webview_active=True,
)
def temp_handle_keyboard_save_screenshot_for_debug(key: str):
    screenshot_service = get_screenshot_service()
    try:
        full_path, file_name = asyncio.run(
            screenshot_service.capture_and_save(
                screenshot_dir=get_screenshots_dir_dep(),
                resolution_profile=get_resolution_profile(),
                should_focus=True,
                post_process=True,
                title="Debug",
                fmt=ScreenshotSaveFormat.PNG,
            )
        )
        logger.info(f"截图已保存到 {full_path}")
        logger.info(f"截图文件名: {file_name}")
    except Exception as e:
        logger.exception(f"截图失败: {e}")


@contextmanager
def bind_hotkeys(server_config: ServerConfig):
    """Context manager to bind and unbind global hotkeys."""
    keyboard.add_hotkey("[", handle_keyboard_single_recognition, args=("[",))
    keyboard.add_hotkey("]", handle_keyboard_auto_click, args=("]",))
    keyboard.add_hotkey("alt+delete", handle_keyboard_on_exit, args=("alt+delete",))
    if server_config.dev_mode:
        logger.debug("开发模式下，启用截图调试热键 `=`")
        keyboard.add_hotkey(
            "=", temp_handle_keyboard_save_screenshot_for_debug, args=("=",)
        )  # 临时热键，用于调试截图功能
    logger.info("全局热键已注册")
    try:
        yield
    finally:
        keyboard.unhook_all()
        logger.info("全局热键已注销")


# only export bind_hotkeys from this module
__all__ = ["bind_hotkeys"]
