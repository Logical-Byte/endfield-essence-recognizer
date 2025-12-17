from __future__ import annotations

import importlib.resources
import time
import winsound
from pathlib import Path

import keyboard

from endfield_essence_recognizer.data import (
    all_attribute_stats,
    all_secondary_stats,
    all_skill_stats,
)
from endfield_essence_recognizer.essence_scanner import EssenceScanner, recognize_once
from endfield_essence_recognizer.log import logger
from endfield_essence_recognizer.recognizer import (
    Recognizer,
    preprocess_text_roi,  # noqa: F401
    preprocess_text_template,  # noqa: F401
)
from endfield_essence_recognizer.window import get_active_support_window

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

supported_window_titles = ["EndfieldTBeta2", "明日方舟：终末地"]
"""支持的窗口标题列表"""

# 全局变量
running = True
"""程序运行状态标志"""
essence_scanner_thread: EssenceScanner | None = None
"""基质扫描器线程实例"""

# 构造识别器实例
text_recognizer = Recognizer(
    labels=all_attribute_stats + all_secondary_stats + all_skill_stats,
    templates_dir=Path(str(generated_template_dir)),
    # preprocess_roi=preprocess_text_roi,
    # preprocess_template=preprocess_text_template,
)
icon_recognizer = Recognizer(
    labels=["deprecated", "not_deprecated", "locked", "not_locked"],
    templates_dir=Path(str(screenshot_template_dir)),
)


def on_bracket_left():
    """处理 "[" 键按下事件 - 仅识别不操作"""
    window = get_active_support_window(supported_window_titles)
    if window is None:
        logger.debug("终末地窗口不在前台，忽略 '[' 键。")
        return
    else:
        logger.info("检测到 '[' 键，开始识别基质")
        recognize_once(window, text_recognizer, icon_recognizer)


def on_bracket_right():
    """处理 "]" 键按下事件 - 切换自动点击"""
    global essence_scanner_thread

    if get_active_support_window(supported_window_titles) is None:
        logger.debug('终末地窗口不在前台，忽略 "]" 键。')
        return
    else:
        if essence_scanner_thread is None or not essence_scanner_thread.is_alive():
            logger.info('检测到 "]" 键，开始扫描基质')
            essence_scanner_thread = EssenceScanner(
                text_recognizer=text_recognizer,
                icon_recognizer=icon_recognizer,
                supported_window_titles=supported_window_titles,
            )
            essence_scanner_thread.start()
            winsound.PlaySound(
                str(enable_sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC
            )
        else:
            logger.info('检测到 "]" 键，停止扫描基质')
            essence_scanner_thread.stop()
            essence_scanner_thread = None
            winsound.PlaySound(
                str(disable_sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC
            )


def on_exit():
    """处理 Alt+Delete 按下事件 - 退出程序"""
    global running, essence_scanner_thread
    logger.info('检测到 "Alt+Delete"，正在退出程序...')
    running = False
    if essence_scanner_thread is not None:
        essence_scanner_thread.stop()
        essence_scanner_thread = None


def main():
    """主函数"""
    global running

    message = """

<white>==================================================</>
<white>终末地基质妙妙小工具已启动</>
<white>==================================================</>
<green><bold>使用前阅读：</></>
  <white>- 请打开终末地<yellow><bold>贵重品库</></>并切换到<yellow><bold>武器基质</></>页面</>
  <white>- 在运行过程中，请确保终末地窗口<yellow><bold>置于前台</></></>
<green><bold>功能介绍：</></>
  <white>- 按 "<green><bold>[</></>" 键识别当前基质，仅识别不操作</>
  <white>- 按 "<green><bold>]</></>" 键扫描所有基质，并自动锁定宝藏基质，解锁垃圾基质</>
  <white>  基质扫描过程中再次按 "<green><bold>]</></>" 键中断扫描</>
  <white>- 按 "<green><bold>Alt+Delete</></>" 退出程序</>
<white>==================================================</>
"""
    logger.opt(colors=True).success(message)

    logger.info("开始监听热键...")

    # 注册热键
    keyboard.add_hotkey("[", on_bracket_left)
    keyboard.add_hotkey("]", on_bracket_right)
    keyboard.add_hotkey("alt+delete", on_exit)

    # 保持程序运行
    try:
        while running:
            time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("程序被中断，正在退出...")
    finally:
        # 清理
        keyboard.unhook_all()
        logger.info("程序已退出")


if __name__ == "__main__":
    main()
