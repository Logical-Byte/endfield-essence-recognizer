from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey

"""
WikiGroupTable 记录了百科的顶层分类信息。

每个百科等级分类WikiGroup都包含若干个WikiGroupEntry，表示该分类下的具体子分类。
"""


class WikiGroupEntry(TypedDict):
    groupId: str
    """
    百科子分类 ID，例如 "wiki_group_weapon_sword"

    该 ID 可用于在 WikiEntryTable 中查找该子分类下的具体百科条目。
    """
    groupName: TranslationKey
    """
    百科子分类名称的翻译键，例如"单手剑"
    """
    iconId: str


class WikiGroup(TypedDict):
    list: list[WikiGroupEntry]


type WikiGroupTable = dict[str, WikiGroup]
"""
我们主要关心对这个字典的wiki_type_weapon访问，它返回了武器百科分类的信息。

武器百科WikiGroup包含了多个WikiGroupEntry，每个表示一个武器子分类，例如单手剑、双手剑等。

"""
