import importlib.resources
import json

from endfield_essence_recognizer.game_data.models.v2 import (
    EssenceGemV2,
    EssenceId,
    WeaponId,
    WeaponTypeId,
    WeaponTypeV2,
    WeaponV2,
)

# helper type alias
type OptEssenceId = EssenceId | None
type EssenceTuple = tuple[OptEssenceId, OptEssenceId, OptEssenceId]


class StaticGameData:
    """
    Manager for static game data (V2).
    Centralizes access to weapons, gems, weapon types, and rarity colors.
    Uses pre-transformed data in src/endfield_essence_recognizer/data/v2/.

    These files are read-only and loaded once on initialization. Therefore
    this class should be accessed as a singleton for efficiency.
    """

    def __init__(self) -> None:
        self._weapons: dict[WeaponId, WeaponV2] = {}
        self._gems: dict[EssenceId, EssenceGemV2] = {}
        self._weapon_types: dict[WeaponTypeId, WeaponTypeV2] = {}
        self._rarity_colors: dict[int, str] = {}

        # Index for faster lookup

        # map weapon_type_id to list of WeaponV2
        self._weapons_by_type: dict[WeaponTypeId, list[WeaponV2]] = {}

        # map (gem1_id, gem2_id, gem3_id) tuple to list of weapon_ids
        self._essence_tuple_to_weapon_ids: dict[EssenceTuple, list[WeaponId]] = {}

        # Load data on initialization, not lazy
        self._load_data()
        self._index_data()

    def _load_data(self) -> None:
        """Loads all V2 JSON data files into internal dictionaries."""
        try:
            data_root = (
                importlib.resources.files("endfield_essence_recognizer") / "data" / "v2"
            )

            # Load Weapons
            weapon_path = data_root / "Weapon.json"
            with importlib.resources.as_file(weapon_path) as weapon_path:
                weapon_data = json.loads(weapon_path.read_text(encoding="utf-8"))
                for w_id, data in weapon_data.items():
                    weapon = WeaponV2(**data)
                    self._weapons[w_id] = weapon

            # Load Gems
            gem_path = data_root / "EssenceGem.json"
            with importlib.resources.as_file(gem_path) as gem_path:
                gem_data = json.loads(gem_path.read_text(encoding="utf-8"))
                for g_id, data in gem_data.items():
                    self._gems[g_id] = EssenceGemV2(**data)

            # Load Weapon Types
            type_path = data_root / "WeaponType.json"
            with importlib.resources.as_file(type_path) as type_path:
                type_data = json.loads(type_path.read_text(encoding="utf-8"))
                for t_id, data in type_data.items():
                    self._weapon_types[int(t_id)] = WeaponTypeV2(**data)

            # Load Rarity Colors
            rarity_path = data_root / "RarityColor.json"
            with importlib.resources.as_file(rarity_path) as rarity_path:
                rarity_data = json.loads(rarity_path.read_text(encoding="utf-8"))
                for r_id, data in rarity_data.items():
                    self._rarity_colors[int(r_id)] = data["color"]
        except Exception as e:
            raise RuntimeError(f"Failed to load static game data V2: {e}") from e

    def _index_data(self) -> None:
        """Builds indexes for faster lookups."""
        # Index weapons by type
        for weapon in self._weapons.values():
            self._weapons_by_type.setdefault(weapon.weapon_type, []).append(weapon)

        # Index weapons by stats
        for weapon in self._weapons.values():
            key = (weapon.gem1_id, weapon.gem2_id, weapon.gem3_id)
            self._essence_tuple_to_weapon_ids.setdefault(key, []).append(
                weapon.weapon_id
            )

    def get_weapon(self, weapon_id: WeaponId) -> WeaponV2 | None:
        """Returns a WeaponV2 by its ID, or None if not found."""
        return self._weapons.get(weapon_id)

    def get_gem(self, gem_id: EssenceId) -> EssenceGemV2 | None:
        """Returns an EssenceGemV2 by its ID, or None if not found."""
        return self._gems.get(gem_id)

    def get_weapon_type(self, type_id: WeaponTypeId) -> WeaponTypeV2 | None:
        """Returns a WeaponTypeV2 by its ID, or None if not found."""
        return self._weapon_types.get(type_id)

    def list_weapons(self) -> list[WeaponV2]:
        """Returns a list of all weapons."""
        return list(self._weapons.values())

    def list_gems(self) -> list[EssenceGemV2]:
        """Returns a list of all gems."""
        return list(self._gems.values())

    def list_weapon_types(self) -> list[WeaponTypeV2]:
        """Returns a list of all weapon types."""
        return list(self._weapon_types.values())

    def get_weapons_by_type(self, type_id: WeaponTypeId) -> list[WeaponV2]:
        """Returns all weapons of a specific type."""
        return self._weapons_by_type.get(type_id, [])

    def find_weapons_by_stats(
        self,
        attr: EssenceId | None = None,
        sec: EssenceId | None = None,
        skill: EssenceId | None = None,
    ) -> list[WeaponId]:
        """
        Returns weapon IDs that match the provided optional gem stats.
        Matches gem1_id with attr, gem2_id with sec, and gem3_id with skill.
        This is an exact match on the tuple; partial matches return empty.

        e.g. find_weapons_by_stats(attr="foo") will search for weapons with
        gem1_id == "foo" and gem2_id == None and gem3_id == None.
        """
        return self._essence_tuple_to_weapon_ids.get((attr, sec, skill), [])

    def get_rarity_color(self, rarity: int) -> str:
        """Returns the hex color code for a given rarity, or white if not found."""
        return self._rarity_colors.get(rarity, "#FFFFFF")
