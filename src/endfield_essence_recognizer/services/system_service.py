from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.utils.log import logger


class SystemService:
    """Service for managing application-level operations."""

    def __init__(self, scanner_service: ScannerService):
        self._scanner_service = scanner_service

    def exit_application(self):
        """Gracefully shut down the application."""
        logger.info("正在执行程序退出流程...")

        # 停止所有正在运行的扫描任务
        if self._scanner_service.is_running():
            logger.debug("正在停止活动扫描任务...")
            self._scanner_service.stop_scan()

        # 关闭 Webview 窗口
        from endfield_essence_recognizer.webui import window

        logger.debug("正在销毁 Webview 窗口...")
        window.destroy()

    def resize_window(self, width: int, height: int) -> None:
        """把主窗口调整为指定尺寸（宽高单位为像素）。

        取值范围由调用方（路由层）保证，这里只负责转交窗口对象。

        Args:
            width: 目标窗口宽度。
            height: 目标窗口高度。
        """
        from endfield_essence_recognizer.webui import window

        logger.debug("正在调整窗口尺寸为 {}×{}...", width, height)
        window.resize(width, height)
