from typing import TypedDict

from ..common import TranslationKey


class WorldEnergyPointGroup(TypedDict):
    firstPassRewardId: str
    gameGroupId: str
    gameGroupName: TranslationKey
    gemCustomItemId: str
    gemRandId: str
    icon: str
    primAttrTermIds: list[str]
    secAttrTermIds: list[str]
    skillTermIds: list[str]
    worldLevel2GameMechanicsIdMap: dict[str, str]


type WorldEnergyPointGroupTable = dict[str, WorldEnergyPointGroup]
