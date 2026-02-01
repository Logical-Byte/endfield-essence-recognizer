"""
FastAPI dependency injection.
"""

from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.services.user_setting_manager import UserSettingManager

__all__ = ["get_user_setting_manager"]

_user_setting_manager = UserSettingManager(user_setting_file=get_config_path())


def get_user_setting_manager() -> UserSettingManager:
    """
    Get the singleton UserSettingManager instance.
    """
    return _user_setting_manager
