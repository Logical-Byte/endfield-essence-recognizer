from typing import TypedDict

from ...common import TranslationKey


class WikiGroupEntry(TypedDict):
    groupId: str
    groupName: TranslationKey
    iconId: str


class WikiGroup(TypedDict):
    list: list[WikiGroupEntry]


type WikiGroupTable = dict[str, WikiGroup]
