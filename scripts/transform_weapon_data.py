"""
Transform raw game data to a more convenient schema.

This script takes the original TableCfg JSON files (e.g.,
WeaponBasicTable.json, ItemTable.json) and transforms them into
a new schema suitable for the app.
"""

import argparse
import json
import os
from typing import Any, TypedDict


class TranslationKey(TypedDict):
    id: str | int
    text: str


def get_cn_text(data: TranslationKey, i18n_table: dict[str, str]) -> str:
    """获取中文翻译，如果没有则返回默认文本"""
    text_id = str(data.get("id", ""))
    if text_id in i18n_table:
        return i18n_table[text_id]
    return data.get("text", "")


def main():
    parser = argparse.ArgumentParser(
        description="Transform raw game data to a new schema."
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Path to input TableCfg directory (containing json files).",
    )
    parser.add_argument("output_dir", type=str, help="Path to output directory.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not write files, only print stats."
    )
    parser.add_argument("--debug", action="store_true", help="Print debug information.")
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    def load_table(name: str) -> Any:
        path = os.path.join(input_dir, f"{name}.json")
        if not os.path.exists(path):
            # Try without .json if input_dir might be pointing to a different structure
            path = os.path.join(input_dir, name)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    print(f"Loading tables from {input_dir}...")
    weapon_basic_table = load_table("WeaponBasicTable")
    item_table = load_table("ItemTable")
    gem_table = load_table("GemTable")
    gem_tag_id_table = load_table("GemTagIdTable")
    skill_patch_table = load_table("SkillPatchTable")
    wiki_group_table = load_table("WikiGroupTable")
    wiki_entry_table = load_table("WikiEntryTable")
    wiki_entry_data_table = load_table("WikiEntryDataTable")
    i18n_table_cn = load_table("I18nTextTable_CN")

    rarity_color_table = load_table("RarityColorTable")

    # 1. Transform WeaponType
    print("Transforming WeaponType...")
    weapon_types = {}
    item_to_weapon_type_id = {}

    # wiki_type_weapon contains list of weapon categories
    weapon_groups = wiki_group_table.get("wiki_type_weapon", {}).get("list", [])
    for i, group in enumerate(weapon_groups):
        # 1-based index (matches WeaponBasic.weaponType)
        # this is based on the order in wiki_type_weapon
        weapon_type_id = i + 1
        wiki_group_id = group.get("groupId")
        name = get_cn_text(group.get("groupName", {}), i18n_table_cn)

        weapon_types[weapon_type_id] = {
            "weapon_type_id": weapon_type_id,
            "wiki_group_id": wiki_group_id,
            "name": name,
            "icon_id": group.get("iconId"),
        }

        # Build reverse mapping from weapon_id to weapon_type_id
        if wiki_group_id in wiki_entry_table:
            entry_ids = wiki_entry_table[wiki_group_id].get("list", [])
            for entry_id in entry_ids:
                entry_data = wiki_entry_data_table.get(entry_id)
                if entry_data and "refItemId" in entry_data:
                    item_to_weapon_type_id[entry_data["refItemId"]] = weapon_type_id

    # 2. Transform EssenceGem
    print("Transforming EssenceGem...")
    essence_gems = {}
    term_type_map = {0: "ATTRIBUTE", 1: "SECONDARY", 2: "SKILL"}

    for gem_term_id, gem_data in gem_table.items():
        name = get_cn_text(gem_data.get("tagName", {}), i18n_table_cn)
        gem_type = term_type_map.get(gem_data.get("termType"), "UNKNOWN")

        essence_gems[gem_term_id] = {
            "gem_id": gem_term_id,
            "name": name,
            "type": gem_type,
        }

    print("Validating weapon type mappings...")
    # check that every weapon has valid raw type and wiki weapon type id
    for wpn_id in weapon_basic_table.keys():
        match weapon_basic_table[wpn_id].get("weaponType"):
            case int() as raw_type if raw_type > 0:
                pass
            case _ as invalid_raw_type:
                print(
                    f"  Warning: Weapon ID {wpn_id} has invalid raw weaponType: {invalid_raw_type}"
                )
        match item_to_weapon_type_id.get(wpn_id):
            case int() as wiki_type if wiki_type > 0:
                pass
            case _ as invalid_wiki_type:
                print(
                    f"  Warning: Weapon ID {wpn_id} has invalid wiki weapon type id: {invalid_wiki_type}"
                )

    # check that raw type id to wiki mapping is consistent
    # i.e. there exists a mapping from raw_type to wiki weapon_type_id
    # for all weapons, e.g. { 1:2, 2:1, 3:3, ... }, no need to be identical
    weapon_id_generator = (
        weapon_id for weapon_id in weapon_basic_table.keys() if weapon_id in item_table
    )
    # wpn_id -> (wpn_id, raw type of weapon, wiki generated weapon type id)
    raw_type_and_wiki_type_generator = (
        (
            weapon_id,
            weapon_basic_table[weapon_id].get("weaponType", -1),
            item_to_weapon_type_id.get(weapon_id, -2),
        )
        for weapon_id in weapon_id_generator
    )
    # build a mapping from raw_type to set of wiki weapon_type_id
    raw_to_wiki_type_map: dict[int, set[int]] = {}
    for _wpn_id, raw_type, wiki_type in raw_type_and_wiki_type_generator:
        if raw_type not in raw_to_wiki_type_map:
            raw_to_wiki_type_map[raw_type] = set()
        raw_to_wiki_type_map[raw_type].add(wiki_type)
    print("Raw Type to Wiki Weapon Type ID mapping:")
    for raw_type, wiki_types in raw_to_wiki_type_map.items():
        wiki_types_list = list(wiki_types)
        wiki_types_name_list = [
            weapon_types[wt_id]["name"] for wt_id in wiki_types_list
        ]
        print(
            f"  Raw Type {raw_type}: Wiki Weapon Types {wiki_types_list} ({wiki_types_name_list})"
        )
        if len(wiki_types) > 1:
            print(
                f"    Warning: Raw Type {raw_type} maps to multiple Wiki Weapon Types: {wiki_types}"
            )

    # 3. Transform Weapon
    print("Transforming Weapon...")
    weapons = {}
    for weapon_id, basic_data in weapon_basic_table.items():
        item_data = item_table.get(weapon_id, {})
        if not item_data:
            continue

        name = get_cn_text(item_data.get("name", {}), i18n_table_cn)
        raw_type = basic_data.get("weaponType", -1)
        weapon_type_id = item_to_weapon_type_id.get(weapon_id, -2)

        rarity = item_data.get("rarity", 0)

        # Resolve skills
        skill_ids = basic_data.get("weaponSkillList", [])
        resolved_skills = {"gem1_id": None, "gem2_id": None, "gem3_id": None}

        for skill_id in skill_ids:
            patch_bundle = skill_patch_table.get(skill_id, {}).get(
                "SkillPatchDataBundle", []
            )
            if not patch_bundle:
                continue

            # Usually we use the first level (0) for tag lookup
            tag_id = patch_bundle[0].get("tagId")
            if not tag_id:
                continue

            gem_term_id = gem_tag_id_table.get(tag_id)
            if not gem_term_id:
                continue

            gem_data = gem_table.get(gem_term_id)
            if not gem_data:
                continue

            term_type = gem_data.get("termType")
            if term_type == 0:
                resolved_skills["gem1_id"] = gem_term_id
            elif term_type == 1:
                resolved_skills["gem2_id"] = gem_term_id
            elif term_type == 2:
                resolved_skills["gem3_id"] = gem_term_id

        weapons[weapon_id] = {
            "weapon_id": weapon_id,
            "name": name,
            # "type": raw_type, # we don't need this raw type
            "weapon_type": weapon_type_id,
            "rarity": rarity,
            "icon_id": item_data.get("iconId"),
            **resolved_skills,
        }

    # transform rarity colors
    print("Transforming Rarity Colors...")
    # preserve the original mapping structure:
    # "1": {"color": "FFFFFF", "rarity": 1}, ...
    rarity_colors = {}
    for rarity, raw_data in rarity_color_table.items():
        try:
            r_int = int(rarity)
            r_color = raw_data.get("color", None)
            if r_color is None:
                print(f"  Warning: Rarity {rarity} has no color defined.")
                continue
            rarity_colors[r_int] = {
                "rarity": r_int,
                "color": f"#{r_color}",
            }
        except ValueError:
            print(f"  Warning: Rarity {rarity} is not a valid integer.")
            continue
    # print summary of rarity colors
    print("Rarity Colors:")
    for rarity, color_info in rarity_colors.items():
        print(f"  Rarity {rarity}: Color {color_info['color']}")

    # 4. Output
    print("\nResults Summary:")
    print(f"  WeaponTypes: {len(weapon_types)}")
    print(f"  EssenceGems: {len(essence_gems)}")
    print(f"  Weapons:     {len(weapons)}")
    print(f"  RarityColors: {len(rarity_colors)}")

    if args.debug:
        import pprint

        print("\nWeaponTypes:")
        pprint.pprint(weapon_types)
        print("\nEssenceGems:")
        pprint.pprint(essence_gems)
        print("\nWeapons:")
        pprint.pprint(weapons)
        print("\nRarityColors:")
        pprint.pprint(rarity_colors)

    if args.dry_run:
        print("\nDry run active. No files written.")
        print("Would write to directory:", os.path.abspath(output_dir))
    else:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        def save_json(name: str, data: dict):
            path = os.path.join(output_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Saved {path}")

        save_json("WeaponType", weapon_types)
        save_json("EssenceGem", essence_gems)
        save_json("Weapon", weapons)
        save_json("RarityColor", rarity_colors)


if __name__ == "__main__":
    main()
