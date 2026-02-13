from typing import TypedDict

from . import (
    gem_table,
    gem_tag_id_table,
    get_translation,
    skill_patch_table,
    weapon_basic_table,
    wiki_entry_data_table,
    wiki_entry_table,
    wiki_group_table,
)
from .models import TranslationKey


class WeaponStats(TypedDict):
    attribute: str | None
    """基础属性"""
    secondary: str | None
    """附加属性"""
    skill: str | None
    """技能属性"""


def get_gem_tag_name(gem_term_id: str, language: str) -> str:
    """Get the localized name for a gem tag."""
    gem = gem_table.get(gem_term_id)
    if gem is None:
        return gem_term_id
    return get_translation(gem["tagName"], language)


def get_stats_for_weapon(weapon_id: str) -> WeaponStats:
    """Get essence stats for a specific weapon."""
    weapon = weapon_basic_table[weapon_id]

    result: WeaponStats = {
        "attribute": None,
        "secondary": None,
        "skill": None,
    }

    for weapon_skill in weapon["weaponSkillList"]:
        skill_patch = skill_patch_table[weapon_skill]
        skill_patch_data = skill_patch["SkillPatchDataBundle"]
        tag_id = skill_patch_data[0]["tagId"]
        gem_stat = gem_tag_id_table[tag_id]
        gem = gem_table[gem_stat]
        term_type = gem["termType"]
        gem_term_id = gem["gemTermId"]

        if term_type == 0:
            result["attribute"] = gem_term_id
        elif term_type == 1:
            result["secondary"] = gem_term_id
        elif term_type == 2:
            result["skill"] = gem_term_id

    return result


all_attribute_stats = [
    gem["gemTermId"] for gem in gem_table.values() if gem.get("termType") == 0
]
all_secondary_stats = [
    gem["gemTermId"] for gem in gem_table.values() if gem.get("termType") == 1
]
all_skill_stats = [
    gem["gemTermId"] for gem in gem_table.values() if gem.get("termType") == 2
]

weapon_stats_dict = {
    weapon_id: get_stats_for_weapon(weapon_id)
    for weapon_id in weapon_basic_table.keys()
}

weapon_type_int_to_translation_key: dict[str, TranslationKey] = {}
for wiki_group in wiki_group_table["wiki_type_weapon"]["list"]:
    for wiki_entry_id in wiki_entry_table[wiki_group["groupId"]]["list"]:
        wiki_entry_data = wiki_entry_data_table[wiki_entry_id]
        weapon_type_int_to_translation_key[wiki_entry_data["refItemId"]] = wiki_group[
            "groupName"
        ]
