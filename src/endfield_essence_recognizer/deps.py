"""
FastAPI dependency injection.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.core.window import (
    SUPPORTED_WINDOW_TITLES,
    WindowManager,
)
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

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
