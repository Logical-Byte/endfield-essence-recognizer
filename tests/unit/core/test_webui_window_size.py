"""窗口尺寸配置读写的单元测试。

窗口必须在主进程加载配置之前确定尺寸，因此这两个函数直接读写 `config.json`。
这里覆盖文件缺失、内容损坏、三种模式分支、越界钳制，以及写回时不得破坏其它配置项。
"""

import json
import os
from pathlib import Path

from endfield_essence_recognizer.core import webui
from endfield_essence_recognizer.schemas.user_setting import UserSetting

# 由 remember_window_size 之外的字段，用来确认写回不会破坏其它配置项
OTHER_SETTING = {"trash_weapon_ids": ["w1"], "auto_page_flip": False}


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


def test_remember_window_size_updates_last_size(tmp_path: Path):
    """记住模式下写回两个尺寸字段，其余配置项原样保留。"""
    path = _write_config(
        tmp_path,
        {
            "version": UserSetting._VERSION,
            "window_size_mode": "remember",
            "window_last_width": 1600,
            "window_last_height": 900,
            **OTHER_SETTING,
        },
    )

    webui.remember_window_size(1280, 720, path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["window_last_width"] == 1280
    assert saved["window_last_height"] == 720
    assert saved["version"] == UserSetting._VERSION
    assert saved["trash_weapon_ids"] == OTHER_SETTING["trash_weapon_ids"]
    assert saved["auto_page_flip"] is OTHER_SETTING["auto_page_flip"]


def test_remember_window_size_clamps_written_size(tmp_path: Path):
    """写回前同样钳制尺寸，避免写出下次加载不合法的值。"""
    path = _write_config(tmp_path, {"window_size_mode": "remember"})

    webui.remember_window_size(10, 999999, path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["window_last_width"] == 400
    assert saved["window_last_height"] == 10000


def test_remember_window_size_skips_other_modes(tmp_path: Path):
    """非记住模式不覆盖用户显式设定的尺寸。"""
    path = _write_config(
        tmp_path,
        {
            "window_size_mode": "custom",
            "window_last_width": 1600,
            "window_last_height": 900,
        },
    )
    before = path.read_text(encoding="utf-8")

    webui.remember_window_size(1280, 720, path)

    assert path.read_text(encoding="utf-8") == before


def test_remember_window_size_skips_missing_config(tmp_path: Path):
    """配置缺失时直接跳过，不写出不完整的配置文件。"""
    path = tmp_path / "config.json"

    webui.remember_window_size(1280, 720, path)

    assert not path.exists()


def test_remember_window_size_skips_unchanged_size(tmp_path: Path):
    """尺寸未变化时不重复写盘。"""
    path = _write_config(
        tmp_path,
        {
            "window_size_mode": "remember",
            "window_last_width": 1280,
            "window_last_height": 720,
        },
    )
    old_time = 1_000_000_000
    os.utime(path, (old_time, old_time))

    webui.remember_window_size(1280, 720, path)

    assert path.stat().st_mtime == old_time
