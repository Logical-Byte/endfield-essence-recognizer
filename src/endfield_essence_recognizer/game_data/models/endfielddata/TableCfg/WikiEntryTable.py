from typing import TypedDict


class WikiEntry(TypedDict):
    list: list[str]
    """
    一系列百科条目 ID 列表，例如 ["wiki_wpn_pistol_0001", "wiki_wpn_pistol_0002", ...]

    它们是 WikiEntryDataTable 的主键，可以用于查找具体的百科条目内容。
    """


type WikiEntryTable = dict[str, WikiEntry]
"""
根据 WikiGroupTable 中的 WikiGroupEntry 的 groupId 映射到该子分类下的具体百科条目ID列表。

例如，"wiki_group_weapon_pistol"映射到的 WikiEntry 对象的 list 包含了所有手枪类武器的百科条目 ID 列表。
"""
