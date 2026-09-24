from typing import TypedDict

from ..common import TranslationKey


class WorldEnergyPoint(TypedDict):
    costStamina: int
    desc: TranslationKey
    enemyIds: list[str]
    enemyLevels: list[int]
    gameCategory: str
    gameGroupId: str
    gameMechanicsId: str
    gameName: TranslationKey
    levelId: str
    probGemItemIds: list[str]
    recommendLv: int
    worldLevel: int


type WorldEnergyPointTable = dict[str, WorldEnergyPoint]
