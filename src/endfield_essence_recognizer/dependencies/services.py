from functools import lru_cache

from fastapi import Depends

from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.services.audio_service import (
    AudioService,
    build_audio_service_profile,
)
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService
from endfield_essence_recognizer.services.static_data_service import StaticDataService
from endfield_essence_recognizer.services.system_service import SystemService

from .window import get_game_window_manager


@lru_cache
def get_audio_service() -> AudioService:
    """
    Get the AudioService singleton.
    """
    return AudioService(build_audio_service_profile())


@lru_cache
def get_scanner_service() -> ScannerService:
    return ScannerService(audio_service=get_audio_service())


@lru_cache
def get_log_service() -> LogService:
    return LogService()


@lru_cache
def get_system_service() -> SystemService:
    return SystemService(scanner_service=get_scanner_service())


@lru_cache
def get_screenshot_service() -> ScreenshotService:
    """
    Get the ScreenshotService singleton.
    """
    return ScreenshotService(get_game_window_manager())


@lru_cache
def get_static_game_data() -> StaticGameData:
    """
    Get the StaticGameData singleton.
    """
    return StaticGameData()


def get_static_data_service(
    static_data: StaticGameData = Depends(get_static_game_data),
) -> StaticDataService:
    """
    Get the StaticDataService singleton.
    """
    return StaticDataService(static_data)
