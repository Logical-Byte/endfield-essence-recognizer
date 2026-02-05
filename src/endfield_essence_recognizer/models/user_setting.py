from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class Action(StrEnum):
    KEEP = "keep"
    LOCK = "lock"
    DEPRECATE = "deprecate"
    UNLOCK = "unlock"
    UNDEPRECATE = "undeprecate"
    UNLOCK_AND_UNDEPRECATE = "unlock_and_undeprecate"


class EssenceStats(BaseModel):
    attribute: str | None
    secondary: str | None
    skill: str | None


class UserSetting(BaseModel):
    _VERSION: ClassVar[int] = 2

    version: int = _VERSION

    trash_weapon_ids: list[str] = []
    treasure_essence_stats: list[EssenceStats] = []

    treasure_action: Action = Action.LOCK
    trash_action: Action = Action.UNLOCK

    high_level_treasure_enabled: bool = False
    """是否启用高等级基质属性词条判定为宝藏"""
    high_level_treasure_attribute_threshold: int = Field(default=3, ge=1, le=6)
    """高等级基础属性词条的等级阈值（+1~+6）"""
    high_level_treasure_secondary_threshold: int = Field(default=3, ge=1, le=6)
    """高等级附加属性词条的等级阈值（+1~+6）"""
    high_level_treasure_skill_threshold: int = Field(default=3, ge=1, le=3)
    """高等级技能属性词条的等级阈值（+1~+3）"""

    def update_from_model(self, other: UserSetting) -> None:
        for field in self.__class__.model_fields:
            setattr(self, field, getattr(other, field))

    def update_from_dict(self, data: dict[str, Any]) -> None:
        model = UserSetting.model_validate(data)
        self.update_from_model(model)
