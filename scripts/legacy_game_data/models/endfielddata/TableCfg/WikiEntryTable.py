from typing import TypedDict


class WikiEntry(TypedDict):
    list: list[str]


type WikiEntryTable = dict[str, WikiEntry]
