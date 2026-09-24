from __future__ import annotations

import json
from typing import TYPE_CHECKING

from endfield_essence_recognizer.game_data.models.v2 import (
    EnergyAlluviumV2,
    EssenceStatV2,
    StatId,
    WeaponId,
    WeaponTypeId,
    WeaponTypeV2,
    WeaponV2,
)

if TYPE_CHECKING:
    from pathlib import Path

# helper type alias
type OptStatId = StatId | None
type StatTuple = tuple[OptStatId, OptStatId, OptStatId]


class StaticGameData:
    """
    Manager for static game data (V2).
    Centralizes access to weapons, stats, weapon types, and rarity colors.
    Uses pre-transformed data in resources/data/v2/.

    These files are read-only and loaded once on initialization. Therefore
    this class should be accessed as a singleton for efficiency.
    """

    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root
        self._weapons: dict[WeaponId, WeaponV2] = {}
        self._stats: dict[StatId, EssenceStatV2] = {}
        self._weapon_types: dict[WeaponTypeId, WeaponTypeV2] = {}
        self._rarity_colors: dict[int, str] = {}
        self._energy_alluviums: dict[str, EnergyAlluviumV2] = {}

        # Index for faster lookup

        # map weapon_type_id to list of WeaponV2
        self._weapons_by_type: dict[WeaponTypeId, list[WeaponV2]] = {}

        # map (stat1_id, stat2_id, stat3_id) tuple to list of weapon_ids
        self._stat_tuple_to_weapon_ids: dict[StatTuple, list[WeaponId]] = {}

        # Load data on initialization, not lazy
        self._load_data()
        self._index_data()

    def _load_data(self) -> None:
        """Loads all V2 JSON data files into internal dictionaries."""
        try:
            # Load Weapons
            weapon_file = self._data_root / "Weapon.json"
            with open(weapon_file, encoding="utf-8") as f:
                weapon_data = json.load(f)
                for w_id, data in weapon_data.items():
                    weapon = WeaponV2(**data)
                    self._weapons[w_id] = weapon

            # Load Stats
            stat_file = self._data_root / "EssenceStat.json"
            with open(stat_file, encoding="utf-8") as f:
                stat_data = json.load(f)
                for s_id, data in stat_data.items():
                    self._stats[s_id] = EssenceStatV2(**data)

            # Load Weapon Types
            type_file = self._data_root / "WeaponType.json"
            with open(type_file, encoding="utf-8") as f:
                type_data = json.load(f)
                for t_id, data in type_data.items():
                    self._weapon_types[WeaponTypeId(t_id)] = WeaponTypeV2(**data)

            # Load Rarity Colors
            rarity_file = self._data_root / "RarityColor.json"
            with open(rarity_file, encoding="utf-8") as f:
                rarity_data = json.load(f)
                for r_id, data in rarity_data.items():
                    self._rarity_colors[int(r_id)] = data["color"]

            # Load Energy Alluviums
            alluvium_file = self._data_root / "EnergyAlluviums.json"
            with open(alluvium_file, encoding="utf-8") as f:
                alluvium_data = json.load(f)
                for _key, data in alluvium_data.items():
                    alluvium = EnergyAlluviumV2(
                        battle_id=data["battleId"],
                        battle_name=data["battleName"],
                        image_url=data.get("imageUrl"),
                        secondary_stats=data["secondaryStats"],
                        skill_stats=data["skillStats"],
                    )
                    self._energy_alluviums[alluvium.battle_id] = alluvium
        except Exception as e:
            raise RuntimeError(f"Failed to load static game data V2: {e}") from e

    def _index_data(self) -> None:
        """Builds indexes for faster lookups."""
        # Index weapons by type
        for weapon in self._weapons.values():
            self._weapons_by_type.setdefault(weapon.weapon_type, []).append(weapon)

        # Index weapons by stats
        for weapon in self._weapons.values():
            key = (weapon.stat1_id, weapon.stat2_id, weapon.stat3_id)
            self._stat_tuple_to_weapon_ids.setdefault(key, []).append(weapon.weapon_id)

    def get_weapon(self, weapon_id: WeaponId) -> WeaponV2 | None:
        """Returns a WeaponV2 by its ID, or None if not found."""
        return self._weapons.get(weapon_id)

    def get_stat(self, stat_id: StatId) -> EssenceStatV2 | None:
        """Returns an EssenceStatV2 by its ID, or None if not found."""
        return self._stats.get(stat_id)

    def get_weapon_type(self, type_id: WeaponTypeId) -> WeaponTypeV2 | None:
        """Returns a WeaponTypeV2 by its ID, or None if not found."""
        return self._weapon_types.get(type_id)

    def list_weapons(self) -> list[WeaponV2]:
        """Returns a list of all weapons."""
        return list(self._weapons.values())

    def list_stats(self) -> list[EssenceStatV2]:
        """Returns a list of all stats."""
        return list(self._stats.values())

    def list_weapon_types(self) -> list[WeaponTypeV2]:
        """Returns a list of all weapon types, sorted by sort_order."""
        return sorted(self._weapon_types.values(), key=lambda x: x.sort_order)

    def get_weapons_by_type(self, type_id: WeaponTypeId) -> list[WeaponV2]:
        """Returns all weapons of a specific type."""
        return self._weapons_by_type.get(type_id, [])

    def find_weapons_by_stats(
        self,
        attr: StatId | None = None,
        sec: StatId | None = None,
        skill: StatId | None = None,
    ) -> list[WeaponId]:
        """
        Returns weapon IDs that match the provided optional stats.
        Matches stat1_id with attr, stat2_id with sec, and stat3_id with skill.
        This is an exact match on the tuple; partial matches return empty.

        e.g. find_weapons_by_stats(attr="foo") will search for weapons with
        stat1_id == "foo" and stat2_id == None and stat3_id == None.
        """
        return self._stat_tuple_to_weapon_ids.get((attr, sec, skill), [])

    def get_rarity_color(self, rarity: int) -> str:
        """Returns the hex color code for a given rarity, or white if not found."""
        return self._rarity_colors.get(rarity, "#FFFFFF")

    def list_energy_alluviums(self) -> list[EnergyAlluviumV2]:
        """Returns a list of all energy alluviums."""
        return list(self._energy_alluviums.values())
