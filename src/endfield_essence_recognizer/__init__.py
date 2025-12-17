from __future__ import annotations

import ctypes
import importlib.resources
import time
from pathlib import Path

import keyboard

from endfield_essence_recognizer.data import (
    all_attribute_stats,
    all_secondary_stats,
    all_skill_stats,
)
from endfield_essence_recognizer.essence_scanner import recognize_once
from endfield_essence_recognizer.log import logger
from endfield_essence_recognizer.recognizer import (
    Recognizer,
    preprocess_text_roi,  # noqa: F401
    preprocess_text_template,  # noqa: F401
)
from endfield_essence_recognizer.window import get_active_support_window

# 资源路径
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

# 构造识别器实例
text_recognizer = Recognizer(
    labels=all_attribute_stats + all_secondary_stats + all_skill_stats,
    templates_dir=Path(str(generated_template_dir)),
    # preprocess_roi=preprocess_text_roi,
    # preprocess_template=preprocess_text_template,
)
icon_recognizer = Recognizer(
    labels=["已弃用", "未弃用", "已锁定", "未锁定"],
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


def on_exit():
    """处理 Alt+Delete 按下事件 - 退出程序"""
    global running
    logger.info('检测到 "Alt+Delete"，正在退出程序...')
    running = False


def main():
    """主函数"""
    global running

    # 设置 DPI 感知，防止高 DPI 缩放问题
    ctypes.windll.user32.SetProcessDPIAware()

    message = """

<white>==================================================</>
<green><bold>终末地基质妙妙小工具已启动</></>
<white>==================================================</>
<green><bold>使用前阅读：</></>
  <white>- 请使用<yellow><bold>管理员权限</></>运行本工具，否则无法捕获全局热键</>
  <white>- 请在终末地的设置中将分辨率调整为 <yellow><bold>1920×1080 窗口</></></>
  <white>- 请按 "<green><bold>N</></>" 键打开终末地<yellow><bold>贵重品库</></>并切换到<yellow><bold>武器基质</></>页面</>
  <white>- 在运行过程中，请确保终末地窗口<yellow><bold>置于前台</></></>

<green><bold>功能介绍：</></>
  <white>- 按 "<green><bold>[</></>" 键识别当前选中的基质是宝藏还是垃圾</>
  <white>- 按 "<green><bold>Alt+Delete</></>" 退出程序</>

  <white><cyan><bold>宝藏基质和垃圾基质：</></>如果这个基质和任何一把武器能对上<dim>（基质的所有属性与至少 1 件已实装武器的属性完全相同）</>，则是宝藏，否则是垃圾。</>
<white>==================================================</>
"""
    logger.opt(colors=True).success(message)

    logger.info("开始监听热键...")

    # 注册热键
    keyboard.add_hotkey("[", on_bracket_left)
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
