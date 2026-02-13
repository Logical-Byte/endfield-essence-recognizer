from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class BlackboardEntry(TypedDict):
    key: str
    value: float
    valueStr: str


class SkillPatchTableItem(TypedDict):
    blackboard: list[BlackboardEntry]
    coolDown: float
    costType: int
    costValue: int
    description: TranslationKey
    iconBgType: int
    iconId: str
    level: int
    maxChargeTime: float
    skillId: str
    skillName: TranslationKey
    subDescList: list[str]
    subDescNameList: list[TranslationKey]
    tagId: str


class SkillPatchDataBundle(TypedDict):
    SkillPatchDataBundle: list[SkillPatchTableItem]


type SkillPatchTable = dict[str, SkillPatchDataBundle]
