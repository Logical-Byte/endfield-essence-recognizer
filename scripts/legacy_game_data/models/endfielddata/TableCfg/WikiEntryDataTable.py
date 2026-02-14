from typing import TypedDict

from ...common import TranslationKey


class WikiEntryData(TypedDict):
    desc: TranslationKey
    groupId: str
    id: str
    order: int
    prtsId: str
    refItemId: str
    refMonsterTemplateId: str


type WikiEntryDataTable = dict[str, WikiEntryData]
