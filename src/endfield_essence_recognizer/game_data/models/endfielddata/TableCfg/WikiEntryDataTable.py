from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


class WikiEntryData(TypedDict):
    desc: TranslationKey
    groupId: str
    id: str
    """
    主键，出现在 WikiEntryTable 的 list 列表中，例如 "wiki_wpn_pistol_0001"
    """
    order: int
    prtsId: str
    refItemId: str
    """
    百科条目所指向的物品 ID (对应 ItemTable)
    对于武器百科条目，这也是武器的 weaponId（对应 WeaponBasicTable）
    """
    refMonsterTemplateId: str


type WikiEntryDataTable = dict[str, WikiEntryData]
