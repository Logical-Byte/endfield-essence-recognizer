"""在游戏窗口中安全测试仓库翻页与基质识别。

该脚本直接运行正式的 ``DraggableScannerEngine``，但把宝藏和养成材料的
处理动作都强制设为 KEEP，因此不会锁定、解锁、弃用或取消弃用基质。

使用前请在游戏中打开：贵重品库 -> 武器基质，并把列表滚动到顶部。

运行方式：
    uv run python scripts/test_inventory_page_flip.py

扫描过程中可按 Ctrl+Shift+Q 请求停止。也可把鼠标迅速移到屏幕左上角，
触发 PyAutoGUI 的紧急停止机制。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from endfield_essence_recognizer.schemas.user_setting import UserSetting


STOP_HOTKEY = "ctrl+shift+q"


@dataclass(frozen=True)
class ReadOnlySettingManager:
    """向扫描引擎提供一份固定的、无状态修改动作的设置。"""

    setting: UserSetting

    def get_user_setting(self) -> UserSetting:
        return self.setting


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="在终末地游戏界面中测试正式的自动翻页和基质识别代码。"
    )
    parser.add_argument(
        "--countdown",
        type=int,
        default=5,
        metavar="SECONDS",
        help="确认后等待多少秒再开始（默认：5）",
    )
    parser.add_argument(
        "--no-row-align",
        action="store_true",
        help="关闭正式扫描默认启用的翻页后网格行对齐修正",
    )
    parser.add_argument(
        "--overscroll-fix",
        action="store_true",
        help="启用实验性的重复首行滚动过量修正",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="不等待回车确认，适合已经准备好游戏界面时使用",
    )
    args = parser.parse_args()
    if args.countdown < 0:
        parser.error("--countdown 不能小于 0")
    return args


def build_context():
    """使用与正式程序相同的工厂创建全部识别器。"""
    from endfield_essence_recognizer.core.scanner.context import ScannerContext
    from endfield_essence_recognizer.dependencies.recognition import (
        get_abandon_status_recognizer_dep,
        get_attribute_level_recognizer_dep,
        get_attribute_recognizer_dep,
        get_lock_status_recognizer_dep,
        get_rarity_recognizer_dep,
        get_skip_marker_detector_dep,
        get_ui_scene_recognizer_dep,
    )
    from endfield_essence_recognizer.dependencies.services import get_static_game_data

    return ScannerContext(
        attr_recognizer=get_attribute_recognizer_dep(),
        attr_level_recognizer=get_attribute_level_recognizer_dep(),
        abandon_status_recognizer=get_abandon_status_recognizer_dep(),
        lock_status_recognizer=get_lock_status_recognizer_dep(),
        skip_marker_detector=get_skip_marker_detector_dep(),
        rarity_recognizer=get_rarity_recognizer_dep(),
        ui_scene_recognizer=get_ui_scene_recognizer_dep(),
        static_game_data=get_static_game_data(),
    )


def make_read_only_settings(
    *, row_align: bool, overscroll_fix: bool
) -> ReadOnlySettingManager:
    from endfield_essence_recognizer.schemas.user_setting import Action, UserSetting

    setting = UserSetting(
        auto_page_flip=True,
        fix_grid_row_offset_after_page_flip=row_align,
        fix_page_flip_overscroll=overscroll_fix,
        treasure_action=Action.KEEP,
        trash_action=Action.KEEP,
    )
    return ReadOnlySettingManager(setting)


def print_countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"将在 {remaining} 秒后开始……", flush=True)
        time.sleep(1)


def main() -> int:
    args = parse_args()

    # 延迟导入：这样执行 --help 时无需初始化 Windows 自动化和识别模型。
    import keyboard
    import pyautogui

    from endfield_essence_recognizer.core.layout.factory import (
        build_resolution_profile,
    )
    from endfield_essence_recognizer.core.scanner.engine import (
        DraggableScannerEngine,
    )
    from endfield_essence_recognizer.core.window.adapter import WindowActionsAdapter
    from endfield_essence_recognizer.core.window.scaling import (
        create_scaling_wrappers,
    )
    from endfield_essence_recognizer.dependencies.window import (
        get_game_window_manager,
    )

    pyautogui.FAILSAFE = True
    window_manager = get_game_window_manager()
    if not window_manager.target_exists:
        print('未找到标题为 "Endfield" 的游戏窗口。请先启动游戏再运行脚本。')
        return 2

    adapter = WindowActionsAdapter(window_manager)
    image_source, window_actions = create_scaling_wrappers(adapter, adapter)
    logical_width, logical_height = image_source.get_client_size()
    profile = build_resolution_profile(logical_width, logical_height)

    print(
        f"已找到游戏窗口：实际 {image_source.physical_size[0]}x"
        f"{image_source.physical_size[1]}，识别坐标 {logical_width}x{logical_height}。"
    )
    print("请确认：")
    print("  1. 游戏已打开“贵重品库 -> 武器基质”页面；")
    print("  2. 基质列表已经滚动到最顶部；")
    print("  3. 当前没有另一个识别扫描正在运行。")
    print("测试只会选择基质和拖动列表，不会改变锁定或弃用状态。")
    print(f"扫描期间按 {STOP_HOTKEY.upper()} 可停止。")

    if not args.yes:
        try:
            input("准备好后按 Enter；按 Ctrl+C 取消：")
        except (EOFError, KeyboardInterrupt):
            print("已取消。")
            return 130

    print("正在加载识别器……", flush=True)
    context = build_context()
    settings = make_read_only_settings(
        row_align=not args.no_row_align,
        overscroll_fix=args.overscroll_fix,
    )
    engine = DraggableScannerEngine(
        ctx=context,
        image_source=image_source,
        window_actions=window_actions,
        user_setting_manager=settings,  # type: ignore[arg-type]
        profile=profile,
    )

    stop_event = threading.Event()
    hotkey_handle = None
    try:
        hotkey_handle = keyboard.add_hotkey(STOP_HOTKEY, stop_event.set)
    except Exception as exc:
        print(f"警告：无法注册全局停止快捷键（{exc}）。仍可使用鼠标左上角急停。")

    try:
        print_countdown(args.countdown)
        engine.execute(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
        print("收到 Ctrl+C，测试已停止。")
        return 130
    except pyautogui.FailSafeException:
        stop_event.set()
        print("已触发鼠标左上角急停，测试已停止。")
        return 130
    finally:
        if hotkey_handle is not None:
            keyboard.remove_hotkey(hotkey_handle)

    if stop_event.is_set():
        print("测试已按请求停止。")
    else:
        print("翻页与识别测试完成。详细过程请查看上方日志。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
