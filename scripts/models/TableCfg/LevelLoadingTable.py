from typing import TypedDict


class LevelLoading(TypedDict):
    bgNameGroup: list[str]
    levelId: str
    mapTags: list[int]
    originOverrideTypeTag: bool
    overrideTypeTags: list[int]
    regionRelated: bool
    regularBgNameGroup: list[str]
    regularTipsKeyGroup: list[str]
    typeTags: list[int]


type LevelLoadingTable = dict[str, LevelLoading]
