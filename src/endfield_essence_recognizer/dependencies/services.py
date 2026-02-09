from functools import lru_cache

from endfield_essence_recognizer.core.webui import get_webview_title
from endfield_essence_recognizer.core.window import (
    SUPPORTED_WINDOW_TITLES,
    WindowManager,
)
from endfield_essence_recognizer.services.audio_service import (
    AudioService,
    build_audio_service_profile,
)
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService


@lru_cache
def get_audio_service() -> AudioService:
    """
    Get the AudioService singleton.
    """
    return AudioService(build_audio_service_profile())


@lru_cache
def get_window_manager_singleton() -> WindowManager:
    """
    Get the singleton WindowManager instance.
    """
    return WindowManager(SUPPORTED_WINDOW_TITLES)


def get_window_manager_dep() -> WindowManager:
    """
    Get the WindowManager dependency.
    """
    return get_window_manager_singleton()


@lru_cache
def get_webview_window_manager() -> WindowManager:
    """
    Get the singleton WindowManager instance for the webview window.
    """
    # Only contain the single webview title
    return WindowManager([get_webview_title()])


@lru_cache
def get_scanner_service() -> ScannerService:
    return ScannerService()


@lru_cache
def get_log_service() -> LogService:
    return LogService()


@lru_cache
def get_screenshot_service() -> ScreenshotService:
    """
    Get the ScreenshotService singleton.
    """
    return ScreenshotService(get_window_manager_singleton())
