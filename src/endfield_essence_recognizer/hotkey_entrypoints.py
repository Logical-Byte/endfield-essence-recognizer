from contextlib import contextmanager
from functools import wraps

import keyboard

from endfield_essence_recognizer.core.config import ServerConfig
from endfield_essence_recognizer.core.interfaces import HotkeyHandler
from endfield_essence_recognizer.models.scanner import TaskType
from endfield_essence_recognizer.utils.http_client import get_hotkey_client
from endfield_essence_recognizer.utils.log import (
    logger,
)


def hotkey_handler():
    """
    Hotkey 触发时的装饰器，用于日志记录。
    """

    def decorator(func: HotkeyHandler) -> HotkeyHandler:
        @wraps(func)
        def wrapper(key: str) -> None:
            logger.debug(f'检测到热键 "{key}" 被按下。')

            try:
                # call the actual handler function
                func(key)

            except Exception as e:
                logger.error(f'处理热键 "{key}" 时发生错误: {e}')
                logger.opt(exception=e).debug("traceback:")

            logger.debug(f'热键 "{key}" 处理完成。')

        return wrapper

    return decorator


@hotkey_handler()
def handle_keyboard_single_recognition(key: str):
    """处理 "[" 键按下事件 - 仅识别不操作"""
    logger.info(f'检测到 "{key}" 键，开始识别基质')
    get_hotkey_client().post("/recognize_once", key_pressed=key)


@hotkey_handler()
def handle_keyboard_auto_click(key: str):
    """处理 "]" 键按下事件 - 切换自动点击"""
    logger.info(f'检测到 "{key}" 键，切换自动点击状态')
    get_hotkey_client().post(
        "/toggle_scanning", json={"task_type": TaskType.ESSENCE}, key_pressed=key
    )


@hotkey_handler()
def handle_keyboard_delivery_claim(key: str):
    """切换自动抢单状态"""
    logger.info(f'检测到 "{key}" 键，切换自动抢单状态')
    get_hotkey_client().post(
        "/toggle_scanning",
        json={"task_type": TaskType.DELIVERY_CLAIM},
        key_pressed=key,
    )


@hotkey_handler()
def handle_keyboard_on_exit(key: str):
    """处理 Alt+Delete 按下事件 - 退出程序"""
    logger.info(f'检测到 "{key}"，正在退出程序...')
    get_hotkey_client().post("/exit", key_pressed=key)


@hotkey_handler()
def temp_handle_keyboard_save_screenshot_for_debug(key: str):
    logger.info(f'检测到 "{key}" 键，正在保存调试截图...')
    get_hotkey_client().post(
        "/take_and_save_screenshot",
        json={
            "should_focus": True,
            "post_process": True,
            "title": "Debug",
            "format": "png",
        },
        key_pressed=key,
    )


@contextmanager
def bind_hotkeys(server_config: ServerConfig):
    """Context manager to bind and unbind global hotkeys."""
    keyboard.add_hotkey("[", handle_keyboard_single_recognition, args=("[",))
    keyboard.add_hotkey("]", handle_keyboard_auto_click, args=("]",))
    keyboard.add_hotkey("\\", handle_keyboard_delivery_claim, args=("\\",))
    keyboard.add_hotkey("alt+delete", handle_keyboard_on_exit, args=("alt+delete",))
    if server_config.dev_mode:
        logger.debug("开发模式下，启用截图调试热键 `=`")
        keyboard.add_hotkey(
            "=", temp_handle_keyboard_save_screenshot_for_debug, args=("=",)
        )  # 临时热键，用于调试截图功能
    logger.info("全局热键已注册")
    _ = get_hotkey_client()  # ensure client is initialized
    try:
        yield
    finally:
        get_hotkey_client().close()
        keyboard.unhook_all()
        logger.info("全局热键已注销")


# only export bind_hotkeys from this module
__all__ = ["bind_hotkeys"]
