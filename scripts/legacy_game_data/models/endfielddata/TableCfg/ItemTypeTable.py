from typing import TypedDict

from ...common import TranslationKey


class ItemType(TypedDict):
    barkWhenGot: bool
    bgType: int
    hideItemInBagToast: bool
    hideNewToast: bool
    itemType: int
    name: TranslationKey
    showCount: bool
    showCountInTips: bool
    storageSpace: int
    unlockSystemType: int
    valuableTabType: int


type ItemTypeTable = dict[str, ItemType]
