"""
FastAPI dependency injection.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

# Config path dependency


def get_config_path_dep() -> Path:
    """
    The dependency to get the config path.
    """
    return get_config_path()


# UserSettingManager dependency


@lru_cache()
def get_user_setting_manager_singleton(user_setting_file: Path) -> UserSettingManager:
    """
    Get the singleton UserSettingManager instance.

    The lru_cache enables testing with different paths in parallel.
    """
    return UserSettingManager(user_setting_file=user_setting_file)


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
