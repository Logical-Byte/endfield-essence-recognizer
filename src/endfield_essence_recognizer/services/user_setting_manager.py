from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["UserSettingManager"]


def _load_user_setting_from_file(
    model_cls: type[UserSetting], path: Path
) -> UserSetting | None:
    """
    Load UserSetting from a file. Return None if loading fails.
    """
    if not path.is_file():
        return None
    try:
        # pydantic model loading
        obj = json.loads(path.read_text(encoding="utf-8"))
        if "version" in obj and obj["version"] == model_cls._VERSION:
            return model_cls.model_validate(obj)
        else:
            return None
    except Exception as e:
        # returning None masks the error, so log it here
        logger.error("Failed to load user setting from file {}: {}", path, e)
        return None


def _save_user_setting_to_file(model: UserSetting, path: Path) -> bool:
    """
    Save the current UserSetting to a file.

    Return True if successful, False otherwise.
    """
    try:
        path.write_text(
            model.model_dump_json(indent=4, ensure_ascii=False), encoding="utf-8"
        )
        return True
    except Exception:
        # Do not log here, let the caller handle it
        return False


class UserSettingManager:
    """
    A singleton class to manage user settings.

    - Holds a UserSetting instance in memory.
    - Provides interfaces to get and update settings.
    - Loads settings from disk and preserves them to disk when changed.
    """

    def __init__(self, user_setting_file: Path) -> None:
        self._user_setting_file = user_setting_file
        self._user_setting = UserSetting()  # In-memory UserSetting instance

    def get_user_setting(self) -> UserSetting:
        """
        Get a copy of the current UserSetting.
        """
        return self._user_setting.model_copy(deep=True)

    def get_user_setting_ref(self) -> UserSetting:
        """
        Get a reference to the current in-memory UserSetting.
        """
        return self._user_setting

    def load_user_setting(self, path: Path | None = None) -> None:
        """
        Load UserSetting from disk into memory.

        If the file does not exist or model validation fails, use default settings.
        If the file do exist but model validation fails, first back up the invalid
        file and then use a default setting.

        If a fresh default setting is used, it will be saved to disk.
        """
        target_path = path or self._user_setting_file
        logger.info("正在尝试加载配置文件：{}", target_path.resolve())
        result = _load_user_setting_from_file(UserSetting, target_path)
        if result is not None:
            self._user_setting = result
            logger.info("加载配置成功。")
            logger.debug("当前配置内容：{}", self._user_setting.model_dump())
            return
        # Handle invalid or non-existing file
        if target_path.is_file():
            # Backup invalid file
            backup_path = target_path.with_suffix(".backup.json")
            # remove existing backup if any
            if backup_path.is_file():
                backup_path.unlink()
            target_path.rename(backup_path)
            logger.warning(
                "配置文件版本不匹配或无效，已备份旧配置到：{}", backup_path.resolve()
            )
            logger.info("创建并使用默认配置。")
        else:
            logger.info("未找到配置文件，使用默认配置。")
        # Use default settings
        self._user_setting = UserSetting()
        # Save default settings to disk
        self.save_user_setting(target_path)

    def save_user_setting(self, path: Path | None = None) -> None:
        """
        Save the current in-memory UserSetting to disk.
        """
        target_path = path or self._user_setting_file
        success = _save_user_setting_to_file(self._user_setting, target_path)
        if not success:
            logger.error(
                "Failed to save user setting to file: {}", target_path.resolve()
            )

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """
        Update the in-memory UserSetting from a dictionary and save to disk.
        """
        if "version" in data and data["version"] != UserSetting._VERSION:
            raise ConfigVersionMismatchError(UserSetting._VERSION, data["version"])
        self._user_setting.update_from_dict(data)
        self.save_user_setting()

    def update_from_user_setting(self, other: UserSetting) -> None:
        """
        Update the in-memory UserSetting from another UserSetting instance
        and save to disk.
        """
        if other.version != UserSetting._VERSION:
            raise ConfigVersionMismatchError(UserSetting._VERSION, other.version)
        self._user_setting.update_from_model(other)
        self.save_user_setting()
