"""
Transform raw game data to a more convenient schema.

This script takes the original TableCfg JSON files (e.g.,
WeaponBasicTable.json, ItemTable.json) and transforms them into
a new schema suitable for the app.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from typing import Any, Literal

    from .models import (
        GemTable,
        GemTagIdTable,
        I18nTextTable,
        ItemTable,
        LevelLoadingTable,
        RarityColorTable,
        SkillPatchTable,
        TranslationKey,
        WeaponBasicTable,
        WikiEntryDataTable,
        WikiEntryTable,
        WikiGroupTable,
        WorldEnergyPointGroupTable,
        WorldEnergyPointTable,
    )


def get_translation(
    text_data: TranslationKey, language: str, i18n_text_tables: dict[str, I18nTextTable]
) -> str:
    """
    获取指定语言的翻译文本
    """
    str_text_id = str(text_data["id"])
    return i18n_text_tables[language][str_text_id]


type WeaponTypeEnum = Literal[
    "SWORD",  # 单手剑
    "CLAYM",  # 双手剑
    "LANCE",  # 长柄武器
    "PISTOL",  # 手铳
    "WAND",  # 施术单元
]


class EnergyAlluvium(TypedDict):
    battleId: str
    battleName: str
    imageUrl: str
    secondaryStats: list[str]
    skillStats: list[str]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Path to input TableCfg directory (containing json files).",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=Path("resources/data/v2"),
        type=Path,
        help="Path to output directory.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not write files, only print stats."
    )
    parser.add_argument("--debug", action="store_true", help="Print debug information.")

    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    def load_table_cfg(name: str) -> Any:
        path = input_dir / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def save_json(name: str, obj: Any):
        path = output_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"Saved {path.resolve()}")

    print(f"Loading tables from {input_dir}...")

    gem_table: GemTable = load_table_cfg("GemTable")
    gem_tag_id_table: GemTagIdTable = load_table_cfg("GemTagIdTable")
    item_table: ItemTable = load_table_cfg("ItemTable")
    level_loading_table: LevelLoadingTable = load_table_cfg("LevelLoadingTable")
    rarity_color_table: RarityColorTable = load_table_cfg("RarityColorTable")
    skill_patch_table: SkillPatchTable = load_table_cfg("SkillPatchTable")
    weapon_basic_table: WeaponBasicTable = load_table_cfg("WeaponBasicTable")
    wiki_entry_data_table: WikiEntryDataTable = load_table_cfg("WikiEntryDataTable")
    wiki_entry_table: WikiEntryTable = load_table_cfg("WikiEntryTable")
    wiki_group_table: WikiGroupTable = load_table_cfg("WikiGroupTable")
    world_energy_point_group_table: WorldEnergyPointGroupTable = load_table_cfg(
        "WorldEnergyPointGroupTable"
    )
    world_energy_point_table: WorldEnergyPointTable = load_table_cfg(
        "WorldEnergyPointTable"
    )

    i18n_text_table_cn: I18nTextTable = load_table_cfg("I18nTextTable_CN")
    i18n_text_tables: dict[str, I18nTextTable] = {"CN": i18n_text_table_cn}

    def get_cn_text(text_data: TranslationKey) -> str:
        """
        获取中文翻译文本
        """
        return get_translation(text_data, "CN", i18n_text_tables)

    # Transform WeaponType
    print("Transforming WeaponType...")
    weapon_types = {}
    item_to_weapon_type_id = {}

    def get_weapon_type_enum(group_type_id: str) -> tuple[WeaponTypeEnum, int]:
        """
        Get a WeaponTypeEnum based on the wiki group type id.

        The group type ids are like `wiki_group_weapon_{}`, where
        the {} is `sword`, `claymores`, `lance`, `pistol`, `wand` for the 5 weapon types.

        Returns a tuple of (WeaponTypeEnum, sort_order), where sort_order is an integer for sorting the weapon types in a consistent order.
        """
        match group_type_id.rsplit("_", maxsplit=1)[-1]:
            case "sword":
                return "SWORD", 1
            case "claymores":
                return "CLAYM", 2
            case "lance":
                return "LANCE", 3
            case "pistol":
                return "PISTOL", 4
            case "wand":
                return "WAND", 5
            case _:
                raise ValueError(f"Unknown weapon group type id: {group_type_id}")

    # wiki_type_weapon contains list of weapon categories
    weapon_groups = wiki_group_table.get("wiki_type_weapon", {}).get("list", [])
    for _, group in enumerate(weapon_groups):
        wiki_group_id = group.get("groupId")
        # use a enum for weapon type id, which is more stable
        weapon_type_id, sort_order = get_weapon_type_enum(wiki_group_id)
        name = get_cn_text(group.get("groupName", {}))

        weapon_types[weapon_type_id] = {
            "weapon_type_id": weapon_type_id,
            "wiki_group_id": wiki_group_id,
            "name": name,
            "icon_id": group.get("iconId"),
            "sort_order": sort_order,
        }

        # Build reverse mapping from weapon_id to weapon_type_id
        if wiki_group_id in wiki_entry_table:
            entry_ids = wiki_entry_table[wiki_group_id].get("list", [])
            for entry_id in entry_ids:
                entry_data = wiki_entry_data_table.get(entry_id)
                if entry_data and "refItemId" in entry_data:
                    item_to_weapon_type_id[entry_data["refItemId"]] = weapon_type_id

    # Transform EssenceStat
    print("Transforming EssenceStat...")
    essence_stats = {}
    term_type_map = {0: "ATTRIBUTE", 1: "SECONDARY", 2: "SKILL"}

    for stat_term_id, stat_data in gem_table.items():
        name = get_cn_text(stat_data.get("tagName", {}))
        stat_type = term_type_map.get(stat_data.get("termType"), "UNKNOWN")

        essence_stats[stat_term_id] = {
            "stat_id": stat_term_id,
            "name": name,
            "type": stat_type,
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
            # now we expect the wiki weapon type id to be a valid enum value
            case "SWORD" | "CLAYM" | "LANCE" | "PISTOL" | "WAND" as wiki_type:
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

    # Transform Weapon
    print("Transforming Weapon...")
    weapons = {}
    for weapon_id, basic_data in weapon_basic_table.items():
        item_data = item_table.get(weapon_id, {})
        if not item_data:
            continue

        name = get_cn_text(item_data.get("name", {}))
        raw_type = basic_data.get("weaponType", -1)
        weapon_type_id = item_to_weapon_type_id.get(weapon_id, -2)

        rarity_str = item_data.get("rarity", 0)

        # Resolve skills
        skill_ids = basic_data.get("weaponSkillList", [])
        resolved_skills: dict[str, str | None] = {
            "stat1_id": None,
            "stat2_id": None,
            "stat3_id": None,
        }

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

            stat_term_id = gem_tag_id_table.get(tag_id)
            if not stat_term_id:
                continue

            stat_data = gem_table.get(stat_term_id)
            if not stat_data:
                continue

            term_type = stat_data.get("termType")
            if term_type == 0:
                resolved_skills["stat1_id"] = stat_term_id
            elif term_type == 1:
                resolved_skills["stat2_id"] = stat_term_id
            elif term_type == 2:
                resolved_skills["stat3_id"] = stat_term_id

        weapons[weapon_id] = {
            "weapon_id": weapon_id,
            "name": name,
            # "type": raw_type, # we don't need this raw type
            "weapon_type": weapon_type_id,
            "rarity": rarity_str,
            "icon_id": item_data.get("iconId"),
            **resolved_skills,
        }

    # Transfrom energy alluviums
    energy_alluviums: dict[str, EnergyAlluvium] = {}
    for group_id, group in world_energy_point_group_table.items():
        world_level_map = group["worldLevel2GameMechanicsIdMap"]

        # 取最高世界等级对应的 mechanicsId，其 gameName 即为 “重度能量淤积点·xxx”
        max_world_level = max(map(int, world_level_map.keys()))
        last_mechanics_id = world_level_map[str(max_world_level)]
        energy_point = world_energy_point_table[last_mechanics_id]

        secondary_stats = group["secAttrTermIds"]
        skill_stats = group["skillTermIds"]

        # 通过 levelId 从 LevelLoadingTable 获取背景图文件名
        level_id = energy_point["levelId"]
        loading_entry = level_loading_table[level_id]
        bg_name = loading_entry["bgNameGroup"][0]
        image_url = f"https://cos.yituliu.cn/endfield/endfielddata/assets/beyond/dynamicassets/gameplay/ui/sprites/loading/{bg_name}.webp"

        energy_alluviums[group_id] = {
            "battleId": group_id,
            "battleName": get_cn_text(energy_point["gameName"]),
            "imageUrl": image_url,
            "secondaryStats": secondary_stats,
            "skillStats": skill_stats,
        }

    # Transform rarity colors
    print("Transforming Rarity Colors...")
    rarity_colors = {}
    for rarity_str, rarity_color_data in rarity_color_table.items():
        rarity = rarity_color_data["rarity"]
        color_without_hash = rarity_color_data["color"]
        rarity_colors[rarity_str] = {
            "rarity": rarity,
            "color": f"#{color_without_hash}",  # prepend `#` to color code
        }

    # Output
    print("\nResults Summary:")
    print(f"  WeaponTypes:     {len(weapon_types)}")
    print(f"  EssenceStats:    {len(essence_stats)}")
    print(f"  Weapons:         {len(weapons)}")
    print(f"  EnergyAlluviums: {len(energy_alluviums)}")
    print(f"  RarityColors:    {len(rarity_colors)}")

    if args.debug:
        import pprint

        print("\nWeaponTypes:")
        pprint.pprint(weapon_types)
        print("\nEssenceStats:")
        pprint.pprint(essence_stats)
        print("\nWeapons:")
        pprint.pprint(weapons)
        print("\nEnergyAlluviums:")
        pprint.pprint(energy_alluviums)
        print("\nRarityColors:")
        pprint.pprint(rarity_colors)

    if args.dry_run:
        print("\nDry run active. No files written.")
        print("Would write to directory:", output_dir.resolve())
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

        save_json("WeaponType", weapon_types)
        save_json("EssenceStat", essence_stats)
        save_json("Weapon", weapons)
        save_json("EnergyAlluviums", energy_alluviums)
        save_json("RarityColor", rarity_colors)


if __name__ == "__main__":
    main()
