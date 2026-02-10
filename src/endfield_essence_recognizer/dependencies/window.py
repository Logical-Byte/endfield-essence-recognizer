from functools import lru_cache

from fastapi import Depends

from endfield_essence_recognizer.core.webui import get_webview_title
from endfield_essence_recognizer.core.window import (
    SUPPORTED_WINDOW_TITLES,
    WindowManager,
)
from endfield_essence_recognizer.exceptions import (
    WindowNotActiveError,
    WindowNotFoundError,
)
from endfield_essence_recognizer.utils.log import logger


@lru_cache
def get_game_window_manager() -> WindowManager:
    """
    Get the singleton WindowManager instance for the game window.
    """
    return WindowManager(SUPPORTED_WINDOW_TITLES)


@lru_cache
def get_webview_window_manager() -> WindowManager:
    """
    Get the singleton WindowManager instance for the webview window.
    """
    # Only contain the single webview title
    return WindowManager([get_webview_title()])


def require_game_window_exists(
    window_manager: WindowManager = Depends(get_game_window_manager),
) -> None:
    """
    确保终末地游戏窗口存在，否则抛出异常。

    Raises:
        WindowNotFoundError: 如果游戏窗口不存在。
    """
    if not window_manager.target_exists:
        logger.error("未检测到终末地窗口，无法执行操作。")
        raise WindowNotFoundError(
            window_manager.supported_titles, "未检测到终末地窗口，无法执行操作。"
        )


def require_game_or_webview_is_active(
    window_manager: WindowManager = Depends(get_game_window_manager),
    webview_window_manager: WindowManager = Depends(get_webview_window_manager),
) -> None:
    """
    确保终末地游戏窗口或 WebView 窗口在前台，否则抛出异常。

    Raises:
        WindowNotActiveError: 如果游戏窗口或 WebView 窗口不在前台。
    """
    if window_manager.target_is_active:
        logger.debug("终末地窗口在前台，允许操作。")
        return
    elif webview_window_manager.target_is_active:
        logger.debug("WebView 窗口在前台，允许操作。")
        return
    else:
        logger.error("前台窗口不是终末地或 WebView，无法执行操作。")
        raise WindowNotActiveError(
            window_manager.supported_titles + webview_window_manager.supported_titles,
            "前台窗口不是终末地或 WebView，无法执行操作。",
        )
