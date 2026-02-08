import threading

from endfield_essence_recognizer.deps import (
    get_scanner_service,
)
from endfield_essence_recognizer.server import get_server
from endfield_essence_recognizer.utils.log import logger
from endfield_essence_recognizer.webui import start_pywebview


def main():
    """主函数"""

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
