from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from endfield_essence_recognizer.core.interfaces import AutomationEngine


class ScannerService:
    """
    A service that manages the lifecycle of the AutomationEngine background thread.

    This service ensures thread-safety using an RLock and provides methods to start,
    stop, and toggle the scanning process. It also ensures that only one scanning
    thread is active at a time by joining old threads before starting new ones.
    """

    def __init__(
        self,
    ) -> None:
        """
        Initialize the ScannerService.
        """
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()  # Event to signal the thread to stop
        self._lock = threading.RLock()  # Reentrant lock for nested locking

    def start_scan(self, scanner_factory: Callable[[], AutomationEngine]) -> None:
        """
        Start the scanning process in a background thread.

        If a scan is already running, a warning is logged and nothing happens.
        If a previous thread exists but is dead, it is joined before a new one is started.

        Args:
            scanner_factory: A callable that returns an AutomationEngine instance.
        """
        with self._lock:
            if self.is_running():
                logger.warning("扫描已在运行中。")
                return

            # If there's a dead thread from a previous run, ensure it's joined
            if self._thread is not None:
                self._thread.join()

            logger.debug("正在启动扫描服务...")
            self._stop_event.clear()
            scanner = scanner_factory()

            self._thread = threading.Thread(
                target=scanner.execute,
                args=(self._stop_event,),
                daemon=True,
                name="ScannerThread",
            )
            logger.debug("Starting scanner thread.")
            self._thread.start()

    def stop_scan(self) -> None:
        """
        Stop the scanning process.

        Sets the stop event and waits for the background thread to join.
        If no scan is running, a warning is logged.
        """
        with self._lock:
            if not self.is_running():
                logger.warning("扫描未在运行。")
                return

            logger.debug("正在停止扫描服务...")
            self._stop_event.set()
            if self._thread is not None:
                self._thread.join()
                logger.debug("Scanner thread joined.")
                self._thread = None

    def is_running(self) -> bool:
        """
        Check if the scanning thread is currently alive.

        Returns:
            True if the thread is active, False otherwise.
        """
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def toggle_scan(self, scanner_factory: Callable[[], AutomationEngine]) -> None:
        """
        Toggle the scanning state.

        Starts the scan if it's not running, or stops it if it is.
        Uses a single lock to ensure atomicity of the toggle operation.

        Args:
            scanner_factory: A callable that returns an AutomationEngine instance. Called if starting a scan.
        """
        # Use a single lock for the whole toggle operation to prevent races
        # between checking and acting. RLock allows us to call start/stop internally.
        with self._lock:
            if self.is_running():
                self.stop_scan()
            else:
                self.start_scan(scanner_factory)
