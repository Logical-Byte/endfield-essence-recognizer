import json
from pathlib import Path
from typing import Any

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.schemas.user_setting import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    WindowSizeMode,
    clamp_window_size,
)
from endfield_essence_recognizer.version import __version__


def get_webview_title() -> str:
    server_config = get_server_config()
    webview_url = server_config.webview_url
    return f"终末地基质妙妙小工具 v{__version__} ({webview_url})"


def read_window_size(config_path: Path | None = None) -> tuple[int, int]:
    """解析启动时应采用的窗口尺寸。

    窗口必须在 `webview.create_window()` 之前确定尺寸，而配置由主进程启动后
    才由 `UserSettingManager` 加载并迁移，因此这里直接容错读取 `config.json`：
    文件缺失、JSON 损坏或字段类型不符时一律回落到默认尺寸，不抛异常也不写盘。

    Args:
        config_path: 配置文件路径，默认为程序根目录下的 `config.json`。

    Returns:
        (width, height) 窗口宽高，单位为像素。
    """
    setting = _load_setting_dict(config_path or get_config_path())
    if setting is None:
        return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT

    mode = setting.get("window_size_mode")
    if mode == WindowSizeMode.CUSTOM.value:
        return clamp_window_size(
            setting.get("window_width"), setting.get("window_height")
        )
    if mode == WindowSizeMode.REMEMBER.value:
        return clamp_window_size(
            setting.get("window_last_width"), setting.get("window_last_height")
        )
    return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT


def _load_setting_dict(config_path: Path) -> dict[str, Any] | None:
    """容错读取 `config.json`，文件缺失或内容不是 JSON 对象时返回 None。"""
    try:
        setting = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return setting if isinstance(setting, dict) else None
