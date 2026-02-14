from typing import TypedDict


class RarityColor(TypedDict):
    color: str
    rarity: int


type RarityColorTable = dict[str, RarityColor]
