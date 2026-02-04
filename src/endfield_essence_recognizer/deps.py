"""
FastAPI dependency injection.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from endfield_essence_recognizer.core.layout.base import ResolutionProfile
from endfield_essence_recognizer.core.layout.res_1080p import Resolution1080p
from endfield_essence_recognizer.core.path import get_config_path
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
    build_scanner_context,
)
from endfield_essence_recognizer.core.window import (
    SUPPORTED_WINDOW_TITLES,
    WindowManager,
)
from endfield_essence_recognizer.services.scanner_service import ScannerService
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


@lru_cache()
def get_resolution_profile() -> ResolutionProfile:
    """
    Get the ResolutionProfile instance.
    """
    return Resolution1080p()


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


# Config path dependency


def get_config_path_dep() -> Path:
    """
    The dependency to get the config path.
    """
    return get_config_path()


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


@lru_cache()
def get_scanner_service_singleton() -> ScannerService:
    from endfield_essence_recognizer.essence_scanner import EssenceScanner

    def scanner_factory() -> EssenceScanner:
        return EssenceScanner(
            ctx=build_scanner_context(),
            window_manager=get_window_manager_singleton(),
            user_setting_manager=default_user_setting_manager(),
            profile=get_resolution_profile(),
        )

    return ScannerService(scanner_factory=scanner_factory)


def get_scanner_service_dep() -> ScannerService:
    """
    Get the ScannerService dependency.
    """
    return get_scanner_service_singleton()


# Recognizer dependencies


def get_attribute_recognizer_dep() -> AttributeRecognizer:
    """
    Get the default attribute Recognizer instance.
    """
    return prepare_attribute_recognizer()


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


# ScannerContext dependency
def get_scanner_context_dep(
    attr_recognizer: AttributeRecognizer = Depends(get_attribute_recognizer_dep),
    attr_level_recognizer: AttributeLevelRecognizer = Depends(
        prepare_attribute_level_recognizer
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
    Get the default ScannerContext instance.
    """
    return ScannerContext(
        attr_recognizer=attr_recognizer,
        attr_level_recognizer=attr_level_recognizer,
        abandon_status_recognizer=abandon_status_recognizer,
        lock_status_recognizer=lock_status_recognizer,
        ui_scene_recognizer=ui_scene_recognizer,
    )
