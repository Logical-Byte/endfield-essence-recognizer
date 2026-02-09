from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager


@lru_cache
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
    user_setting_file: Path = Depends(get_config_path),
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
