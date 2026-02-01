from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Literal, Self
from warnings import deprecated

from pydantic import BaseModel

from endfield_essence_recognizer.core.path import get_config_path
from endfield_essence_recognizer.utils.log import logger

type Action = Literal[
    "keep",
    "lock",
    "deprecate",
    "unlock",
    "undeprecate",
    "unlock_and_undeprecate",
]


class EssenceStats(BaseModel):
    attribute: str | None
    secondary: str | None
    skill: str | None


class UserSetting(BaseModel):
    _VERSION: ClassVar[int] = 0

    version: int = _VERSION

    trash_weapon_ids: list[str] = []
    treasure_essence_stats: list[EssenceStats] = []

    treasure_action: Action = "lock"
    trash_action: Action = "unlock"

    high_level_treasure_enabled: bool = False
    """是否启用高等级基质属性词条判定为宝藏"""
    high_level_treasure_threshold: int = 3
    """高等级基质属性词条的等级阈值 (+3 或 +4)"""

    def update_from_model(self, other: UserSetting) -> None:
        for field in self.__class__.model_fields:
            setattr(self, field, getattr(other, field))

    def update_from_dict(self, data: dict[str, Any]) -> None:
        model = UserSetting.model_validate(data)
        self.update_from_model(model)

    @classmethod
    @deprecated("Use UserSettingManager instead.")
    def load(cls, config_path: Path | None = None) -> Self:
        config_path = config_path or get_config_path()
        if config_path.is_file():
            logger.info(f"正在加载配置文件：{config_path.resolve()}")
            obj = json.loads(config_path.read_text(encoding="utf-8"))
            if "version" in obj and obj["version"] == cls._VERSION:
                config = cls.model_validate(obj)
                logger.info(f"已加载配置文件：{config!r}")
            else:
                logger.warning("配置文件版本不匹配，已忽略旧配置。")
                config = cls()
                config.save()
        else:
            logger.info("未找到配置文件，使用默认配置。")
            config = cls()
            config.save()
        return config

    @deprecated("Use UserSettingManager instead.")
    def load_and_update(self, config_path: Path | None = None) -> None:
        loaded_config = self.load(config_path=config_path)
        self.update_from_model(loaded_config)

    @deprecated("Use UserSettingManager instead.")
    def save(self, config_path: Path | None = None) -> None:
        config_path = config_path or get_config_path()
        config_path.write_text(
            self.model_dump_json(indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"配置已保存到文件：{config_path.resolve()}")


config = UserSetting()
