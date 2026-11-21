import json
from pathlib import Path
from typing import Any

from endfield_essence_recognizer.core.config import get_server_config
from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.schemas.user_setting import (
    WINDOW_HEIGHT_MAX,
    WINDOW_HEIGHT_MIN,
    WINDOW_WIDTH_MAX,
    WINDOW_WIDTH_MIN,
    WindowSizeMode,
)
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__

DEFAULT_WINDOW_WIDTH = 1600
DEFAULT_WINDOW_HEIGHT = 900


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
        return _normalize_size(
            setting.get("window_width"), setting.get("window_height")
        )
    if mode == WindowSizeMode.REMEMBER.value:
        return _normalize_size(
            setting.get("window_last_width"), setting.get("window_last_height")
        )
    return DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT


def remember_window_size(
    width: int, height: int, config_path: Path | None = None
) -> None:
    """把当前窗口尺寸记录到配置，供下次启动恢复。

    仅在「记住上次大小」模式下写回，避免覆盖用户显式设定的自定义尺寸。写回时
    只改动两个尺寸字段，其余内容原样保留；配置无法读取时直接跳过，避免写出一份
    不完整的配置文件。

    Args:
        width: 当前窗口宽度（像素）。
        height: 当前窗口高度（像素）。
        config_path: 配置文件路径，默认为程序根目录下的 `config.json`。
    """
    target_path = config_path or get_config_path()
    setting = _load_setting_dict(target_path)
    if setting is None:
        return
    if setting.get("window_size_mode") != WindowSizeMode.REMEMBER.value:
        return

    last_width, last_height = _normalize_size(width, height)
    if (
        setting.get("window_last_width") == last_width
        and setting.get("window_last_height") == last_height
    ):
        # 尺寸没变，省掉一次写盘
        return

    setting["window_last_width"] = last_width
    setting["window_last_height"] = last_height
    try:
        target_path.write_text(
            json.dumps(setting, indent=4, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.warning("记录窗口尺寸失败：{}", exc)


def _load_setting_dict(config_path: Path) -> dict[str, Any] | None:
    """容错读取 `config.json`，文件缺失或内容不是 JSON 对象时返回 None。"""
    try:
        setting = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return setting if isinstance(setting, dict) else None


def _normalize_size(width: Any, height: Any) -> tuple[int, int]:
    """把尺寸钳制到允许范围，类型不符的一维回落到默认尺寸。"""
    return (
        _clamp_dimension(
            width, WINDOW_WIDTH_MIN, WINDOW_WIDTH_MAX, DEFAULT_WINDOW_WIDTH
        ),
        _clamp_dimension(
            height, WINDOW_HEIGHT_MIN, WINDOW_HEIGHT_MAX, DEFAULT_WINDOW_HEIGHT
        ),
    )


def _clamp_dimension(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    """钳制单个维度；`bool` 是 `int` 的子类，需要单独排除。"""
    if not isinstance(value, int) or isinstance(value, bool):
        return fallback
    return max(minimum, min(maximum, value))
