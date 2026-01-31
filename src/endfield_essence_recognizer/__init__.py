from __future__ import annotations

import importlib.resources
from typing import TYPE_CHECKING, cast

from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.version import __version__ as __version__

if TYPE_CHECKING:
    import threading

    from endfield_essence_recognizer.essence_scanner import EssenceScanner
    from endfield_essence_recognizer.recognizer import Recognizer


# 资源路径
enable_sound_path = (
    importlib.resources.files("endfield_essence_recognizer") / "sounds/enable.wav"
)
disable_sound_path = (
    importlib.resources.files("endfield_essence_recognizer") / "sounds/disable.wav"
)
generated_template_dir = (
    importlib.resources.files("endfield_essence_recognizer") / "templates/generated"
)
screenshot_template_dir = (
    importlib.resources.files("endfield_essence_recognizer") / "templates/screenshot"
)

supported_window_titles = ["Endfield"]
"""支持的窗口标题列表"""

# 全局变量
essence_scanner_thread: EssenceScanner | None = None
"""基质扫描器线程实例"""
server_thread: threading.Thread | None = None
"""后端服务器线程实例"""

# 构造识别器实例
text_recognizer: Recognizer | None = None
icon_recognizer: Recognizer | None = None


def on_bracket_left():
    """处理 "[" 键按下事件 - 仅识别不操作"""
    from endfield_essence_recognizer.essence_scanner import recognize_once
    from endfield_essence_recognizer.utils.window import get_active_support_window

    window = get_active_support_window(supported_window_titles)
    if window is None:
        logger.debug("终末地窗口不在前台，忽略 '[' 键。")
        return
    else:
        logger.info("检测到 '[' 键，开始识别基质")
        recognize_once(window, text_recognizer, icon_recognizer)  # type: ignore


def toggle_scan():
    """切换基质扫描状态"""
    import winsound

    from endfield_essence_recognizer.essence_scanner import EssenceScanner

    global essence_scanner_thread

    if essence_scanner_thread is None or not essence_scanner_thread.is_alive():
        logger.info("开始扫描基质")
        essence_scanner_thread = EssenceScanner(
            text_recognizer=cast("Recognizer", text_recognizer),
            icon_recognizer=cast("Recognizer", icon_recognizer),
            supported_window_titles=supported_window_titles,
        )
        essence_scanner_thread.start()
        with importlib.resources.as_file(
            enable_sound_path
        ) as enable_sound_path_ensured:
            winsound.PlaySound(
                str(enable_sound_path_ensured),
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
    else:
        logger.info("停止扫描基质")
        essence_scanner_thread.stop()
        essence_scanner_thread = None
        with importlib.resources.as_file(
            disable_sound_path
        ) as disable_sound_path_ensured:
            winsound.PlaySound(
                str(disable_sound_path_ensured),
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )


def on_bracket_right():
    """处理 "]" 键按下事件 - 切换自动点击"""
    from endfield_essence_recognizer.utils.window import get_active_support_window

    global essence_scanner_thread

    if get_active_support_window(supported_window_titles) is None:
        logger.debug('终末地窗口不在前台，忽略 "]" 键。')
        return
    else:
        toggle_scan()


def on_exit():
    """处理 Alt+Delete 按下事件 - 退出程序"""
    global essence_scanner_thread

    logger.info('检测到 "Alt+Delete"，正在退出程序...')

    # 关闭 webview 窗口，剩下的清理工作交给 main 函数
    from endfield_essence_recognizer.webui import window

    window.destroy()


def main():
    """主函数"""

    global text_recognizer, icon_recognizer, essence_scanner_thread

    # 打印欢迎信息
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
  - 按 "<green><bold>]</></>" 键扫描所有基质，并自动锁定宝藏基质，解锁其他基质
    基质扫描过程中再次按 "<green><bold>]</></>" 键中断扫描
  - 按 "<green><bold>Alt+Delete</></>" 退出程序

  <cyan><bold>宝藏基质和养成材料：</></>可以在设置界面自定义。默认情况下，如果这个基质和任何一把武器能对上，则是宝藏，否则是养成材料。
==================================================
"""
    logger.opt(colors=True).info(message)

    # 读取配置
    from endfield_essence_recognizer.config import config

    config.load_and_update()

    # 构造识别器实例
    from endfield_essence_recognizer.game_data.weapon import (
        all_attribute_stats,
        all_secondary_stats,
        all_skill_stats,
    )
    from endfield_essence_recognizer.recognizer import Recognizer

    text_recognizer = Recognizer(
        labels=all_attribute_stats + all_secondary_stats + all_skill_stats,
        templates_dir=generated_template_dir,
        # preprocess_roi=preprocess_text_roi,
        # preprocess_template=preprocess_text_template,
    )
    icon_recognizer = Recognizer(
        labels=["已弃用", "未弃用", "已锁定", "未锁定"],
        templates_dir=screenshot_template_dir,
    )

    # 注册热键
    import keyboard

    keyboard.add_hotkey("[", on_bracket_left)
    keyboard.add_hotkey("]", on_bracket_right)
    keyboard.add_hotkey("alt+delete", on_exit)

    logger.info("开始监听热键...")

    # 启动 web 后端
    import threading

    from endfield_essence_recognizer.server import get_server

    server = get_server()
    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )
    server_thread.start()

    # 启动 webview
    from endfield_essence_recognizer.webui import start_pywebview

    try:
        start_pywebview()
        logger.info("Webview 窗口已关闭，正在退出程序...")

    finally:
        # 停止基质扫描线程
        if essence_scanner_thread is not None and essence_scanner_thread.is_alive():
            essence_scanner_thread.stop()
            essence_scanner_thread = None

        # 关闭后端
        server.should_exit = True
        server_thread.join()

        # 解除热键绑定
        keyboard.unhook_all()
        logger.info("程序已退出。")


if __name__ == "__main__":
    main()
