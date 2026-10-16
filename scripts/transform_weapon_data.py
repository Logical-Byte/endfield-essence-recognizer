"""
Transform raw game data to a more convenient schema.

This script takes the original TableCfg JSON files (e.g.,
WeaponBasicTable.json, ItemTable.json) and transforms them into
a new schema suitable for the app.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Literal

    from .models import (
        ForesightWeaponTable,
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

# --------------------------------------------------------------------------- #
# Transformed schema: the JSON files this script writes
# --------------------------------------------------------------------------- #

type WeaponTypeId = Literal[
    "SWORD",  # 单手剑
    "CLAYM",  # 双手剑
    "LANCE",  # 长柄武器
    "PISTOL",  # 手铳
    "WAND",  # 施术单元
]

type EssenceStatType = Literal["ATTRIBUTE", "SECONDARY", "SKILL", "UNKNOWN"]


class WeaponType(TypedDict):
    weapon_type_id: WeaponTypeId
    wiki_group_id: str
    name: str
    icon_id: str
    sort_order: int


class EssenceStat(TypedDict):
    stat_id: str
    name: str
    type: EssenceStatType


class Weapon(TypedDict):
    weapon_id: str
    name: str
    weapon_type: WeaponTypeId
    rarity: int
    icon_id: str
    stat1_id: str | None
    stat2_id: str | None
    stat3_id: str | None


class EnergyAlluvium(TypedDict):
    battleId: str
    battleName: str
    imageUrl: str
    secondaryStats: list[str]
    skillStats: list[str]


class RarityColor(TypedDict):
    rarity: int
    color: str


# --------------------------------------------------------------------------- #
# Raw -> transformed mappings
# --------------------------------------------------------------------------- #

# Trailing segment of a `wiki_group_weapon_*` group id
# -> (weapon type id, sort order).
_WEAPON_TYPE_BY_GROUP_SUFFIX: dict[str, tuple[WeaponTypeId, int]] = {
    "sword": ("SWORD", 1),
    "claymores": ("CLAYM", 2),
    "lance": ("LANCE", 3),
    "pistol": ("PISTOL", 4),
    "wand": ("WAND", 5),
}

# `termType` of a gem (essence stat) -> the transformed stat type.
_GEM_TERM_TYPE_TO_STAT_TYPE: dict[int, EssenceStatType] = {
    0: "ATTRIBUTE",
    1: "SECONDARY",
    2: "SKILL",
}

# `termType` of an essence stat -> the weapon field it fills.
_TERM_TYPE_TO_WEAPON_SLOT: dict[int, str] = {
    0: "stat1_id",
    1: "stat2_id",
    2: "stat3_id",
}

_ALLUVIUM_IMAGE_URL_TEMPLATE = (
    "https://data.akedata.wiki/cdn-cgi/image"
    "/width=660,height=480,format=webp,quality=50"
    "/public/images/assets/beyond"
    "/dynamicassets/gameplay/ui/sprites/loading/{bg_name}.png"
)


# --------------------------------------------------------------------------- #
# Loaded raw tables
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Tables:
    """All raw TableCfg tables required by the transformation."""

    gem: GemTable
    gem_tag_id: GemTagIdTable
    item: ItemTable
    level_loading: LevelLoadingTable
    rarity_color: RarityColorTable
    skill_patch: SkillPatchTable
    foresight_weapon: ForesightWeaponTable
    weapon_basic: WeaponBasicTable
    wiki_entry_data: WikiEntryDataTable
    wiki_entry: WikiEntryTable
    wiki_group: WikiGroupTable
    world_energy_point_group: WorldEnergyPointGroupTable
    world_energy_point: WorldEnergyPointTable
    i18n_text: dict[str, I18nTextTable]


@dataclass(frozen=True, slots=True)
class Output:
    """A single JSON file produced by this script."""

    label: str  # human readable name, used in logs
    filename: str  # file stem, e.g. `WeaponType` -> `WeaponType.json`
    data: Any


@dataclass(frozen=True, slots=True)
class WeaponTypeIndex:
    """Weapon types and the mappings derived from the raw weapon tables."""

    # The `WeaponType.json` content, keyed by weapon type id.
    weapon_types: dict[WeaponTypeId, WeaponType]
    # Weapon item id -> weapon type id, via the wiki entry tables.
    item_to_weapon_type: dict[str, WeaponTypeId]
    # Raw `weaponType` -> the wiki weapon type ids it resolves to.
    raw_to_weapon_types: dict[int, set[WeaponTypeId]]


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


def load_tables(input_dir: Path) -> Tables:
    """Load every raw TableCfg table needed by the transformation."""

    def load(name: str) -> Any:
        with open(input_dir / f"{name}.json", encoding="utf-8") as f:
            return json.load(f)

    return Tables(
        gem=load("GemTable"),
        gem_tag_id=load("GemTagIdTable"),
        item=load("ItemTable"),
        level_loading=load("LevelLoadingTable"),
        rarity_color=load("RarityColorTable"),
        skill_patch=load("SkillPatchTable"),
        foresight_weapon=load("ForesightWeaponTable"),
        weapon_basic=load("WeaponBasicTable"),
        wiki_entry_data=load("WikiEntryDataTable"),
        wiki_entry=load("WikiEntryTable"),
        wiki_group=load("WikiGroupTable"),
        world_energy_point_group=load("WorldEnergyPointGroupTable"),
        world_energy_point=load("WorldEnergyPointTable"),
        i18n_text={"CN": load("I18nTextTable_CN")},
    )


def save_json(output_dir: Path, name: str, obj: Any) -> None:
    """Write `obj` to `<output_dir>/<name>.json` with stable formatting."""
    path = output_dir / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"Saved {path.resolve()}")


def build_text_getter(
    i18n_text_tables: dict[str, I18nTextTable], language: str
) -> Callable[[TranslationKey], str]:
    """
    Build a callable resolving a `TranslationKey` into localized text.

    Keys that have no translation yet (foresight data uses `id: 0`) fall back to
    the text embedded in the key itself, which is usually empty.
    """
    table = i18n_text_tables[language]

    def get_text(text_data: TranslationKey) -> str:
        return table.get(str(text_data["id"]), text_data["text"])

    return get_text


def build_weapon_type_index(
    tables: Tables, get_text: Callable[[TranslationKey], str]
) -> WeaponTypeIndex:
    """Build the weapon types and every mapping derived from them."""
    weapon_types = _build_weapon_types(tables, get_text)
    item_to_weapon_type = _build_item_to_weapon_type(tables, weapon_types)
    raw_to_weapon_types = _build_raw_to_weapon_types(tables, item_to_weapon_type)
    return WeaponTypeIndex(weapon_types, item_to_weapon_type, raw_to_weapon_types)


def _build_weapon_types(
    tables: Tables, get_text: Callable[[TranslationKey], str]
) -> dict[WeaponTypeId, WeaponType]:
    """
    Build the weapon type table.

    Source group ids look like `wiki_group_weapon_sword`; the trailing segment
    identifies the weapon archetype.
    """
    print("Transforming WeaponType...")

    weapon_types: dict[WeaponTypeId, WeaponType] = {}
    for group in tables.wiki_group.get("wiki_type_weapon", {}).get("list", []):
        wiki_group_id = group["groupId"]
        suffix = wiki_group_id.rsplit("_", maxsplit=1)[-1]
        try:
            weapon_type_id, sort_order = _WEAPON_TYPE_BY_GROUP_SUFFIX[suffix]
        except KeyError:
            raise ValueError(f"Unknown weapon group type id: {wiki_group_id}") from None

        weapon_types[weapon_type_id] = {
            "weapon_type_id": weapon_type_id,
            "wiki_group_id": wiki_group_id,
            "name": get_text(group["groupName"]),
            "icon_id": group["iconId"],
            "sort_order": sort_order,
        }

    return weapon_types


def _build_item_to_weapon_type(
    tables: Tables, weapon_types: dict[WeaponTypeId, WeaponType]
) -> dict[str, WeaponTypeId]:
    """Map every weapon item id to a weapon type via the wiki entry tables."""
    item_to_weapon_type: dict[str, WeaponTypeId] = {}

    for weapon_type in weapon_types.values():
        wiki_group_id = weapon_type["wiki_group_id"]
        for entry_id in tables.wiki_entry.get(wiki_group_id, {}).get("list", []):
            entry_data = tables.wiki_entry_data.get(entry_id)
            if entry_data is not None and "refItemId" in entry_data:
                ref_item_id = entry_data["refItemId"]
                item_to_weapon_type[ref_item_id] = weapon_type["weapon_type_id"]

    return item_to_weapon_type


def _build_raw_to_weapon_types(
    tables: Tables, item_to_weapon_type: dict[str, WeaponTypeId]
) -> dict[int, set[WeaponTypeId]]:
    """
    Group the raw `weaponType` of every released weapon by the wiki type it maps to.

    A raw type should resolve to exactly one wiki type; several means the wiki
    groups disagree.
    """
    raw_to_weapon_types: dict[int, set[WeaponTypeId]] = {}

    for weapon_id, basic_data in tables.weapon_basic.items():
        if weapon_id not in tables.item:
            continue

        raw_type = basic_data.get("weaponType")
        wiki_type = item_to_weapon_type.get(weapon_id)
        if not (isinstance(raw_type, int) and raw_type > 0) or wiki_type is None:
            continue

        raw_to_weapon_types.setdefault(raw_type, set()).add(wiki_type)

    return raw_to_weapon_types


def build_essence_stats(
    tables: Tables, get_text: Callable[[TranslationKey], str]
) -> dict[str, EssenceStat]:
    """Build the essence stat table from the gem table."""
    print("Transforming EssenceStat...")

    return {
        stat_term_id: {
            "stat_id": stat_term_id,
            "name": get_text(stat_data["tagName"]),
            "type": _GEM_TERM_TYPE_TO_STAT_TYPE.get(stat_data["termType"], "UNKNOWN"),
        }
        for stat_term_id, stat_data in tables.gem.items()
    }


def _stat_slots_from_term_ids(
    tables: Tables, stat_term_ids: list[str | None]
) -> dict[str, str | None]:
    """
    Distribute essence stat ids into the weapon's three stat slots.

    The stat's `termType` decides whether it fills the attribute, the secondary
    or the skill slot.
    """
    stats: dict[str, str | None] = {
        "stat1_id": None,
        "stat2_id": None,
        "stat3_id": None,
    }

    for stat_term_id in stat_term_ids:
        stat_data = tables.gem.get(stat_term_id) if stat_term_id else None
        if stat_data is None:
            continue

        slot = _TERM_TYPE_TO_WEAPON_SLOT.get(stat_data["termType"])
        if slot is not None:
            stats[slot] = stat_term_id

    return stats


def _skill_stat_term_ids(
    tables: Tables, weapon_skill_list: list[str]
) -> list[str | None]:
    """Resolve every weapon skill to the essence stat it patches."""
    stat_term_ids: list[str | None] = []

    for skill_id in weapon_skill_list:
        patch_bundle = tables.skill_patch.get(skill_id, {}).get(
            "SkillPatchDataBundle", []
        )
        if not patch_bundle:
            continue

        # The first level is enough to look up the stat tag.
        tag_id = patch_bundle[0].get("tagId")
        if not tag_id:
            continue

        stat_term_ids.append(tables.gem_tag_id.get(tag_id))

    return stat_term_ids


def resolve_weapon_stats(
    tables: Tables, weapon_skill_list: list[str]
) -> dict[str, str | None]:
    """
    Resolve the three stat slots (attribute / secondary / skill) of a weapon.

    Every weapon skill patches exactly one essence stat.
    """
    return _stat_slots_from_term_ids(
        tables, _skill_stat_term_ids(tables, weapon_skill_list)
    )


def build_weapons(
    tables: Tables,
    get_text: Callable[[TranslationKey], str],
    index: WeaponTypeIndex,
) -> dict[str, Weapon]:
    """Build the weapon table from the released weapon tables."""
    print("Transforming Weapon...")

    weapons: dict[str, Weapon] = {}
    for weapon_id, basic_data in tables.weapon_basic.items():
        item_data = tables.item.get(weapon_id)
        if not item_data:
            continue

        # Weapons missing a wiki weapon type are dropped: a weapon without a
        # type cannot be matched against anything downstream.
        weapon_type = index.item_to_weapon_type.get(weapon_id)
        if weapon_type is None:
            print(f"  Warning: Weapon ID {weapon_id} has no wiki weapon type, skipped")
            continue

        stats = resolve_weapon_stats(tables, basic_data["weaponSkillList"])
        weapons[weapon_id] = {
            "weapon_id": weapon_id,
            "name": get_text(item_data["name"]),
            "weapon_type": weapon_type,
            "rarity": item_data["rarity"],
            "icon_id": item_data["iconId"],
            "stat1_id": stats["stat1_id"],
            "stat2_id": stats["stat2_id"],
            "stat3_id": stats["stat3_id"],
        }

    return weapons


def build_energy_alluviums(
    tables: Tables, get_text: Callable[[TranslationKey], str]
) -> dict[str, EnergyAlluvium]:
    """Build the energy alluvium table (重度能量淤积点)."""
    alluviums: dict[str, EnergyAlluvium] = {}

    for group_id, group in tables.world_energy_point_group.items():
        # Use the highest world level: its game name is the displayed one,
        # e.g. "重度能量淤积点·枢纽区".
        world_level_map = group["worldLevel2GameMechanicsIdMap"]
        highest_world_level = max(map(int, world_level_map))
        energy_point = tables.world_energy_point[
            world_level_map[str(highest_world_level)]
        ]

        # The loading screen background is derived from the battle's level.
        bg_name = tables.level_loading[energy_point["levelId"]]["bgNameGroup"][0]

        alluviums[group_id] = {
            "battleId": group_id,
            "battleName": get_text(energy_point["gameName"]),
            "imageUrl": _ALLUVIUM_IMAGE_URL_TEMPLATE.format(bg_name=bg_name),
            "secondaryStats": group["secAttrTermIds"],
            "skillStats": group["skillTermIds"],
        }

    return alluviums


def build_rarity_colors(tables: Tables) -> dict[str, RarityColor]:
    """Build the rarity color table."""
    print("Transforming Rarity Colors...")

    return {
        rarity_key: {
            "rarity": rarity_color["rarity"],
            "color": f"#{rarity_color['color']}",
        }
        for rarity_key, rarity_color in tables.rarity_color.items()
    }


def report_weapon_type_mapping(tables: Tables, index: WeaponTypeIndex) -> None:
    """Warn about weapons with missing types, then print the raw -> wiki mapping."""
    print("Validating weapon type mappings...")

    for weapon_id, basic_data in tables.weapon_basic.items():
        raw_type = basic_data.get("weaponType")
        if not (isinstance(raw_type, int) and raw_type > 0):
            print(
                f"  Warning: Weapon ID {weapon_id} has invalid raw weaponType: {raw_type}"
            )

        wiki_type = index.item_to_weapon_type.get(weapon_id)
        if wiki_type is None:
            print(
                f"  Warning: Weapon ID {weapon_id} has invalid wiki weapon type id: {wiki_type}"
            )

    print("Raw Type to Wiki Weapon Type ID mapping:")
    for raw_type, wiki_types in index.raw_to_weapon_types.items():
        sorted_types = sorted(wiki_types)
        names = [index.weapon_types[wt_id]["name"] for wt_id in sorted_types]
        print(f"  Raw Type {raw_type}: Wiki Weapon Types {sorted_types} ({names})")
        if len(wiki_types) > 1:
            print(
                f"    Warning: Raw Type {raw_type} maps to multiple Wiki Weapon Types: {wiki_types}"
            )


def build_foresight_weapons(
    tables: Tables,
    get_text: Callable[[TranslationKey], str],
    index: WeaponTypeIndex,
    known_weapon_ids: set[str],
) -> dict[str, Weapon]:
    """
    Build the weapons that only the foresight (前瞻) table knows about.

    `ForesightWeaponTable` carries weapons that are announced but are still
    absent from `WeaponBasicTable`/`ItemTable`. Weapons already produced from the
    regular tables are left alone, so only the missing ones are added here.
    """
    print("Transforming ForesightWeapon...")

    weapons: dict[str, Weapon] = {}
    for weapon_id, foresight in tables.foresight_weapon.items():
        if weapon_id in known_weapon_ids:
            continue

        raw_type = foresight["wpnType"]
        wiki_types = index.raw_to_weapon_types.get(raw_type)
        if wiki_types is None or len(wiki_types) != 1:
            print(
                f"  Warning: Weapon ID {weapon_id} has ambiguous wiki weapon type "
                f"for raw weaponType {raw_type}: {wiki_types}"
            )
            continue

        name = get_text(foresight["name"])
        if not name:
            print(f"  Warning: Weapon ID {weapon_id} has no name, skipped")
            continue

        (weapon_type,) = wiki_types
        stats = _stat_slots_from_term_ids(
            tables,
            [tables.gem_tag_id.get(tag_id) for tag_id in foresight["gemTagIds"]],
        )

        weapons[weapon_id] = {
            "weapon_id": foresight["weaponId"],
            "name": name,
            "weapon_type": weapon_type,
            "rarity": foresight["rarity"],
            "icon_id": foresight["iconId"],
            "stat1_id": stats["stat1_id"],
            "stat2_id": stats["stat2_id"],
            "stat3_id": stats["stat3_id"],
        }

    if weapons:
        print(f"  Added {len(weapons)} foresight weapon(s): {', '.join(weapons)}")
    else:
        print("  No new foresight weapon.")

    return weapons


def main() -> None:
    args = build_argument_parser().parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    print(f"Loading tables from {input_dir}...")
    tables = load_tables(input_dir)
    get_text = build_text_getter(tables.i18n_text, "CN")

    weapon_type_index = build_weapon_type_index(tables, get_text)
    essence_stats = build_essence_stats(tables, get_text)
    report_weapon_type_mapping(tables, weapon_type_index)

    weapons = build_weapons(tables, get_text, weapon_type_index)
    weapons.update(
        build_foresight_weapons(tables, get_text, weapon_type_index, set(weapons))
    )

    energy_alluviums = build_energy_alluviums(tables, get_text)
    rarity_colors = build_rarity_colors(tables)

    outputs = [
        Output("WeaponTypes", "WeaponType", weapon_type_index.weapon_types),
        Output("EssenceStats", "EssenceStat", essence_stats),
        Output("Weapons", "Weapon", weapons),
        Output("EnergyAlluviums", "EnergyAlluviums", energy_alluviums),
        Output("RarityColors", "RarityColor", rarity_colors),
    ]

    print("\nResults Summary:")
    label_width = max(len(f"{output.label}:") for output in outputs)
    for output in outputs:
        label = f"{output.label}:"
        print(f"  {label:<{label_width}} {len(output.data)}")

    if args.debug:
        import pprint

        for output in outputs:
            print(f"\n{output.label}:")
            pprint.pprint(output.data)

    if args.dry_run:
        print("\nDry run active. No files written.")
        print("Would write to directory:", output_dir.resolve())
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for output in outputs:
        save_json(output_dir, output.filename, output.data)


if __name__ == "__main__":
    main()
