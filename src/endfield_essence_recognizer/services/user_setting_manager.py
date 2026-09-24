from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.schemas.user_setting import UserSetting
from endfield_essence_recognizer.utils.log import logger

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["UserSettingManager"]


def _load_user_setting_from_file(
    model_cls: type[UserSetting], path: Path
) -> tuple[UserSetting | None, bool]:
    """
    Load UserSetting from a file. Return (result, migrated).
    - result: UserSetting or None if loading fails
    - migrated: True if migration from an older version was performed
    """
    if not path.is_file():
        return None, False
    try:
        # pydantic model loading
        obj = json.loads(path.read_text(encoding="utf-8"))
        if "version" in obj:
            if obj["version"] == model_cls._VERSION:
                model = model_cls.model_validate(obj)
                normalized = (
                    obj.get("update_mirror") == "cn"
                    or obj.get("update_flow") == "cn"
                    or "update_flow" not in obj
                    or "update_github_mirror" not in obj
                )
                return model, normalized
            else:
                # 尝试从旧版本迁移
                try:
                    logger.info(
                        f"检测到旧版本配置 (v{obj['version']})，尝试迁移到 v{model_cls._VERSION}"
                    )
                    return model_cls.migrate_from_old_version(obj), True
                except Exception as e:
                    logger.warning(f"配置迁移失败: {e}")
                    return None, False
        else:
            return None, False
    except Exception as e:
        # returning None masks the error, so log it here
        logger.error("Failed to load user setting from file {}: {}", path, e)
        return None, False


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

    def _cleanup_old_backups(self, config_path: Path, keep: int = 3) -> None:
        """清理旧备份文件，保留最近 N 个"""
        pattern = f"{config_path.stem}.backup.*.json"
        backups = sorted(
            config_path.parent.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_backup in backups[keep:]:
            try:
                old_backup.unlink()
                logger.debug("已删除旧备份：{}", old_backup)
            except Exception as e:
                logger.warning("删除旧备份失败 {}: {}", old_backup, e)

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
        result, migrated = _load_user_setting_from_file(UserSetting, target_path)
        if result is not None:
            self._user_setting = result
            ids_assigned = self.ensure_custom_stat_ids()
            # 仅在发生迁移时保存新版本
            if migrated or ids_assigned:
                self.save_user_setting(target_path)
                logger.info("配置已从旧版本迁移并保存。")
            else:
                logger.info("加载配置成功。")
            logger.debug("当前配置内容：{}", self._user_setting.model_dump())
            return
        # Handle invalid or non-existing file
        if target_path.is_file():
            # Backup invalid file with timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = target_path.with_suffix(f".backup.{timestamp}.json")
            target_path.rename(backup_path)
            logger.error(
                "配置文件加载失败，已备份到：{}\n"
                "将使用默认配置。如需恢复旧配置，请检查备份文件。",
                backup_path.resolve(),
            )
            # 清理旧备份，保留最近 3 个
            self._cleanup_old_backups(target_path, keep=3)
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
        self.ensure_custom_stat_ids()
        self.save_user_setting()

    def update_from_user_setting(self, other: UserSetting) -> None:
        """
        Update the in-memory UserSetting from another UserSetting instance
        and save to disk.
        """
        if other.version != UserSetting._VERSION:
            raise ConfigVersionMismatchError(UserSetting._VERSION, other.version)
        self._user_setting.update_from_model(other)
        self.ensure_custom_stat_ids()
        self.save_user_setting()

    def ensure_custom_stat_ids(self) -> bool:
        """为缺少稳定 ID 的自定义基质补齐 ID（就地修改，不写盘）。

        兼容三种情况：旧配置全部缺 ID、客户端新增条目未带 ID、以及手工编辑
        配置导致的 ID 重复。补齐顺序即列表顺序，因此补齐后的 `id` 列表可以
        直接当作"旧下标 → 新 ID"的迁移映射。

        Returns:
            是否发生了变更（调用方据此决定是否需要写盘）。
        """
        changed = False
        seen: set[str] = set()
        for stat in self._user_setting.treasure_essence_stats:
            if not stat.id or stat.id in seen:
                stat.id = uuid4().hex
                changed = True
            seen.add(stat.id)
        return changed

    def get_custom_stat_ids(self) -> list[str]:
        """按当前顺序返回自定义基质的稳定 ID 列表。

        下标即该条目在旧格式 `custom_stat_{index}` 中的编号，供 profile 迁移使用。
        """
        return [stat.id for stat in self._user_setting.treasure_essence_stats]

    def reset_to_default(self) -> UserSetting:
        """
        Reset the in-memory UserSetting to defaults (UserSetting()) and save.

        Returns:
            A deep copy of the reset UserSetting.
        """
        self._user_setting = UserSetting()
        self.save_user_setting()
        logger.info("配置已重置为默认值。")
        return self._user_setting.model_copy(deep=True)
