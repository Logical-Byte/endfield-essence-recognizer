from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel

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
