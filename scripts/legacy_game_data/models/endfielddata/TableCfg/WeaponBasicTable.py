from typing import TypedDict

from ...common import TranslationKey


class WeaponBasic(TypedDict):
    breakthroughTemplateId: str
    engName: TranslationKey
    levelTemplateId: str
    maxLv: int
    modelPath: str
    potentialUpItemList: list[str]
    rarity: int
    talentTemplateId: str
    weaponDesc: TranslationKey
    weaponId: str
    weaponPotentialSkill: str
    weaponSkillList: list[str]
    weaponType: int


type WeaponBasicTable = dict[str, WeaponBasic]
