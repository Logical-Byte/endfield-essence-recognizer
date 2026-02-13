from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class Gem(TypedDict):
    gemTermId: str
    isSkillTerm: bool
    sortOrder: int
    tagDesc: TranslationKey
    tagIcon: str
    tagId: str
    tagName: TranslationKey
    termType: int


type GemTable = dict[str, Gem]
