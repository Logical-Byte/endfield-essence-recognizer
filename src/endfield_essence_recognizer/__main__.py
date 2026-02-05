import threading

from endfield_essence_recognizer.deps import (
    default_user_setting_manager,
    get_scanner_service,
)
from endfield_essence_recognizer.server import get_server
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.webui import start_pywebview


def main():
    """主函数"""

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
  - 按 "<green><bold>]</></>" 键扫描所有基质，并根据设置，自动锁定或者解锁基质
    基质扫描过程中再次按 "<green><bold>]</></>" 键中断扫描
  - 按 "<green><bold>Alt+Delete</></>" 退出程序

  <cyan><bold>宝藏基质和养成材料：</></>可以在设置界面自定义。默认情况下，如果这个基质和任何一把武器能对上，则是宝藏，否则是养成材料。
==================================================
"""
    logger.opt(colors=True).info(message)

    user_setting_manager = default_user_setting_manager()
    user_setting_manager.load_user_setting()

    # 启动 web 后端
    server = get_server()
    server_thread = threading.Thread(
        target=server.run,
        daemon=True,
    )
    server_thread.start()

    # 启动 webview
    try:
        start_pywebview()
        logger.info("Webview 窗口已关闭，正在退出程序...")

    finally:
        # 停止基质扫描线程
        scanner_service = get_scanner_service()
        if scanner_service.is_running():
            scanner_service.stop_scan()

        # 关闭后端
        server.should_exit = True
        server_thread.join()

        # Life cycle shutdown in server will handle hotkeys
        logger.info("程序已退出。")


if __name__ == "__main__":
    main()
