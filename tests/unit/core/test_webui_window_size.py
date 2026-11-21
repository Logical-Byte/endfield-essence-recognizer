"""启动窗口尺寸解析的单元测试。

窗口必须在主进程加载配置之前确定尺寸，因此 `read_window_size` 直接容错读取
`config.json`。这里覆盖文件缺失、内容损坏、三种模式分支与越界钳制；写回一侧
由 `UserSettingManager.remember_window_size` 负责，其测试见
`tests/test_user_setting_manager.py`。
"""

import json
from pathlib import Path

from endfield_essence_recognizer.core import webui


def _write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_read_window_size_without_config_uses_default(tmp_path: Path):
    """配置文件不存在时使用默认尺寸，而不是抛异常。"""
    assert webui.read_window_size(tmp_path / "missing.json") == (
        webui.DEFAULT_WINDOW_WIDTH,
        webui.DEFAULT_WINDOW_HEIGHT,
    )


def test_read_window_size_with_corrupt_json_uses_default(tmp_path: Path):
    """JSON 损坏时使用默认尺寸。"""
    path = tmp_path / "config.json"
    path.write_text("{ not json", encoding="utf-8")

    assert webui.read_window_size(path) == (
        webui.DEFAULT_WINDOW_WIDTH,
        webui.DEFAULT_WINDOW_HEIGHT,
    )


def test_read_window_size_default_mode_ignores_size_fields(tmp_path: Path):
    """默认模式固定使用默认尺寸，即使配置里存着别的宽高。"""
    path = _write_config(
        tmp_path,
        {"window_size_mode": "default", "window_width": 1000, "window_height": 700},
    )

    assert webui.read_window_size(path) == (
        webui.DEFAULT_WINDOW_WIDTH,
        webui.DEFAULT_WINDOW_HEIGHT,
    )


def test_read_window_size_custom_mode_uses_configured_size(tmp_path: Path):
    """自定义模式读取 window_width / window_height。"""
    path = _write_config(
        tmp_path,
        {"window_size_mode": "custom", "window_width": 1000, "window_height": 700},
    )

    assert webui.read_window_size(path) == (1000, 700)


def test_read_window_size_remember_mode_uses_last_size(tmp_path: Path):
    """记住模式读取 window_last_width / window_last_height。"""
    path = _write_config(
        tmp_path,
        {
            "window_size_mode": "remember",
            "window_width": 1000,
            "window_height": 700,
            "window_last_width": 1280,
            "window_last_height": 720,
        },
    )

    assert webui.read_window_size(path) == (1280, 720)


def test_read_window_size_clamps_out_of_range_values(tmp_path: Path):
    """越界尺寸被钳制到允许范围，类型不符的一维回落到默认值。"""
    path = _write_config(
        tmp_path,
        {
            "window_size_mode": "custom",
            "window_width": 10,
            "window_height": "1080",
        },
    )

    assert webui.read_window_size(path) == (400, webui.DEFAULT_WINDOW_HEIGHT)

    path = _write_config(
        tmp_path,
        {"window_size_mode": "custom", "window_width": 10, "window_height": 999999},
    )

    assert webui.read_window_size(path) == (400, 10000)
