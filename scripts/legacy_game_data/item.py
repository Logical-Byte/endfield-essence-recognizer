from . import get_translation, item_table


def get_item_name(item_id: str, language: str) -> str:
    item = item_table.get(item_id)
    if item is None:
        return item_id
    return get_translation(item["name"], language)
