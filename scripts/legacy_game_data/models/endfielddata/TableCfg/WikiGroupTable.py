from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class WikiGroupEntry(TypedDict):
    groupId: str
    groupName: TranslationKey
    iconId: str


class WikiGroup(TypedDict):
    list: list[WikiGroupEntry]


type WikiGroupTable = dict[str, WikiGroup]
