from typing import TypedDict

from ..common import TranslationKey


class ForesightWeaponStageMaterial(TypedDict):
    stageId: int
    upBrkCnt: list[int]
    upBrkIds: list[str]
    upColCnt: list[int]
    upColIds: list[str]
    upExpCnt: list[int]
    upExpIds: list[str]
    upGoldCnt: list[int]
    upGoldIds: list[str]
    upPreCnt: list[int]
    upPreIds: list[str]


class ForesightWeapon(TypedDict):
    gemTagIds: list[str]
    iconId: str
    name: TranslationKey
    rarity: int
    skIds: list[str]
    skNames: list[TranslationKey]
    stageMaterials: dict[str, ForesightWeaponStageMaterial]
    tgtLv: int
    weaponId: str
    wpnType: int


type ForesightWeaponTable = dict[str, ForesightWeapon]
