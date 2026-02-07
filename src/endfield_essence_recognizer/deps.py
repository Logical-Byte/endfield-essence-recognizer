"""
FastAPI dependency injection.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.path import get_config_path, get_screenshots_dir
from endfield_essence_recognizer.core.recognition import (
    AbandonStatusRecognizer,
    AttributeLevelRecognizer,
    AttributeRecognizer,
    LockStatusRecognizer,
    UISceneRecognizer,
    prepare_abandon_status_recognizer,
    prepare_attribute_level_recognizer,
    prepare_attribute_recognizer,
    prepare_lock_status_recognizer,
    prepare_ui_scene_recognizer,
)
from endfield_essence_recognizer.core.scanner.context import (
    ScannerContext,
)
from endfield_essence_recognizer.core.scanner.engine import ScannerEngine
from endfield_essence_recognizer.core.webui import get_webview_title
from endfield_essence_recognizer.core.window import (
    SUPPORTED_WINDOW_TITLES,
    WindowManager,
)
from endfield_essence_recognizer.core.window.adapter import WindowActionsAdapter
from endfield_essence_recognizer.services.audio_service import (
    AudioService,
    build_audio_service_profile,
)
from endfield_essence_recognizer.services.log_service import LogService
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.screenshot_service import ScreenshotService
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


@lru_cache()
def get_resolution_profile() -> ResolutionProfile:
    """
    Get the ResolutionProfile instance.
    """
    return Resolution1080p()


# AudioService dependency


@lru_cache()
def get_audio_service() -> AudioService:
    """
    Get the AudioService singleton.
    """
    return AudioService(build_audio_service_profile())


# WindowManager dependency


@lru_cache()
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


@lru_cache()
def get_webview_window_manager() -> WindowManager:
    """
    Get the singleton WindowManager instance for the webview window.
    """
    # Only contain the single webview title
    return WindowManager([get_webview_title()])


# Path dependency


def get_config_path_dep() -> Path:
    """
    The dependency to get the config path.
    """
    return get_config_path()


def get_screenshots_dir_dep() -> Path:
    """
    The dependency to get the screenshots directory path.
    """
    return get_screenshots_dir()


# UserSettingManager dependency


@lru_cache()
def _get_user_setting_manager_cached(file: Path) -> UserSettingManager:
    return UserSettingManager(user_setting_file=file)


def get_user_setting_manager_singleton(user_setting_file: Path) -> UserSettingManager:
    """
    Get the singleton UserSettingManager instance.

    The lru_cache enables testing with different paths in parallel.
    """
    absolute_path = user_setting_file.resolve()
    # Avoid different path representations of the same file
    return _get_user_setting_manager_cached(absolute_path)


def get_user_setting_manager_dep(
    user_setting_file: Path = Depends(get_config_path_dep),
) -> UserSettingManager:
    """
    Get the singleton UserSettingManager instance.
    """
    return get_user_setting_manager_singleton(user_setting_file)


def default_user_setting_manager() -> UserSettingManager:
    """
    Get the default singleton UserSettingManager instance.
    """
    return get_user_setting_manager_singleton(get_config_path())


# Recognizer dependencies


def get_attribute_recognizer_dep() -> AttributeRecognizer:
    """
    Get the default attribute Recognizer instance.
    """
    return prepare_attribute_recognizer()


def get_attribute_level_recognizer_dep() -> AttributeLevelRecognizer:
    """
    Get the default attribute level Recognizer instance.
    """
    return prepare_attribute_level_recognizer()


def get_abandon_status_recognizer_dep() -> AbandonStatusRecognizer:
    """
    Get the default abandon status Recognizer instance.
    """
    return prepare_abandon_status_recognizer()


def get_lock_status_recognizer_dep() -> LockStatusRecognizer:
    """
    Get the default lock status Recognizer instance.
    """
    return prepare_lock_status_recognizer()


def get_ui_scene_recognizer_dep() -> UISceneRecognizer:
    """
    Get the default UI scene Recognizer instance.
    """
    return prepare_ui_scene_recognizer()


# Scanner-related dependencies


def default_scanner_context() -> ScannerContext:
    """
    Get the default ScannerContext instance.

    Some functions need a ScannerContext but are not called within FastAPI request context.
    So we provide this default builder function.
    """
    return ScannerContext(
        attr_recognizer=prepare_attribute_recognizer(),
        attr_level_recognizer=prepare_attribute_level_recognizer(),
        abandon_status_recognizer=prepare_abandon_status_recognizer(),
        lock_status_recognizer=prepare_lock_status_recognizer(),
        ui_scene_recognizer=prepare_ui_scene_recognizer(),
    )


def get_scanner_context_dep(
    attr_recognizer: AttributeRecognizer = Depends(get_attribute_recognizer_dep),
    attr_level_recognizer: AttributeLevelRecognizer = Depends(
        get_attribute_level_recognizer_dep
    ),
    abandon_status_recognizer: AbandonStatusRecognizer = Depends(
        get_abandon_status_recognizer_dep
    ),
    lock_status_recognizer: LockStatusRecognizer = Depends(
        get_lock_status_recognizer_dep
    ),
    ui_scene_recognizer: UISceneRecognizer = Depends(get_ui_scene_recognizer_dep),
) -> ScannerContext:
    """
    Get a ScannerContext instance.
    """
    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
    )


def get_scanner_engine_dep(
    ctx: ScannerContext = Depends(get_scanner_context_dep),
    window_manager: WindowManager = Depends(get_window_manager_dep),
    user_setting_manager: UserSettingManager = Depends(get_user_setting_manager_dep),
    profile: ResolutionProfile = Depends(get_resolution_profile),
) -> ScannerEngine:
    """
    Get a ScannerEngine instance.

    Note this dependency depends on ResolutionProfile, which will help multi-resolution
    support in the future.
    """
    adapter = WindowActionsAdapter(window_manager)
    return ScannerEngine(
        ctx=ctx,
        image_source=adapter,
        window_actions=adapter,
        user_setting_manager=user_setting_manager,
        profile=profile,
    )


def default_scanner_engine() -> ScannerEngine:
    """
    Get the default ScannerEngine instance.

    Some functions need a ScannerEngine but are not called within FastAPI request context.
    So we provide this default builder function.
    """
    window_manager = get_window_manager_singleton()
    adapter = WindowActionsAdapter(window_manager)
    return ScannerEngine(
        ctx=default_scanner_context(),
        image_source=adapter,
        window_actions=adapter,
        user_setting_manager=default_user_setting_manager(),
        profile=get_resolution_profile(),
    )


@lru_cache()
def get_scanner_service() -> ScannerService:
    return ScannerService()


@lru_cache()
def get_log_service() -> LogService:
    return LogService()


@lru_cache()
def get_screenshot_service() -> ScreenshotService:
    """
    Get the ScreenshotService singleton.
    """
    return ScreenshotService(get_window_manager_singleton())
