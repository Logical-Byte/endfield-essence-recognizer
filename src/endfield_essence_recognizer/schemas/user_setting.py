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
    DEPRECATE_IF_NOT_LOCKED = "deprecate_if_not_locked"
    LOCK_IF_NOT_DEPRECATED = "lock_if_not_deprecated"


class NonFiveStarBehavior(StrEnum):
    """Enumeration of behaviors for non-5-star essences.

    5-star 即高纯基质（黄色），非5-star即非高纯基质。
    """

    PROCESS = "process"
    """Process non-5-star essences normally according to other rules."""

    SKIP = "skip"
    """Skip any operations on non-5-star essences."""


class EssenceStats(BaseModel):
    attribute: str | None
    secondary: str | None
    skill: str | None


class UserSetting(BaseModel):
    _VERSION: ClassVar[int] = 3

    version: int = _VERSION

    trash_weapon_ids: list[str] = []
    treasure_essence_stats: list[EssenceStats] = []

    treasure_action: Action = Action.LOCK
    trash_action: Action = Action.UNLOCK

    non_five_star_behavior: NonFiveStarBehavior = NonFiveStarBehavior.PROCESS
    """如何处理非高纯基质：正常处理或直接跳过。"""

    high_level_treasure_enabled: bool = False
    """是否启用高等级基质属性词条判定为宝藏"""
    high_level_treasure_attribute_threshold: int = Field(default=3, ge=1, le=6)
    """高等级基础属性词条的等级阈值（+1~+6）"""
    high_level_treasure_secondary_threshold: int = Field(default=3, ge=1, le=6)
    """高等级附加属性词条的等级阈值（+1~+6）"""
    high_level_treasure_skill_threshold: int = Field(default=3, ge=1, le=3)
    """高等级技能属性词条的等级阈值（+1~+3）"""

    auto_page_flip: bool = True
    """扫描时是否自动翻页"""

    def update_from_model(self, other: UserSetting) -> None:
        for field in self.__class__.model_fields:
            setattr(self, field, getattr(other, field))

    def update_from_dict(self, data: dict[str, Any]) -> None:
        model = UserSetting.model_validate(data)
        self.update_from_model(model)
