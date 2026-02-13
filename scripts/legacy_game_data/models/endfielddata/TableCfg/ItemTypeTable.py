from typing import TypedDict

from endfield_essence_recognizer.game_data.models.common import TranslationKey


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
