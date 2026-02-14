import json

import pytest

from endfield_essence_recognizer.game_data.models.v2 import WeaponTypeId
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData


@pytest.fixture
def mock_data_root(tmp_path):
    # Weapons
    weapon_data = {
        "weapon_1": {
            "weapon_id": "weapon_1",
            "name": "Weapon 1",
            "weapon_type": "SWORD",
            "rarity": 4,
            "icon_id": "icon_1",
            "stat1_id": "stat_a",
            "stat2_id": "stat_b",
            "stat3_id": None,
        }
    }
    (tmp_path / "Weapon.json").write_text(json.dumps(weapon_data), encoding="utf-8")

    # Stats
    stat_data = {
        "stat_a": {"stat_id": "stat_a", "name": "Stat A", "type": "ATTRIBUTE"},
        "stat_b": {"stat_id": "stat_b", "name": "Stat B", "type": "SECONDARY"},
    }
    (tmp_path / "EssenceStat.json").write_text(json.dumps(stat_data), encoding="utf-8")

    # Weapon Types
    type_data = {
        "SWORD": {
            "weapon_type_id": "SWORD",
            "name": "Sword",
            "wiki_group_id": "group_1",
            "icon_id": "icon_t1",
        }
    }
    (tmp_path / "WeaponType.json").write_text(json.dumps(type_data), encoding="utf-8")

    # Rarity Colors
    rarity_data = {"4": {"color": "#9452FA"}}
    (tmp_path / "RarityColor.json").write_text(
        json.dumps(rarity_data), encoding="utf-8"
    )

    return tmp_path


@pytest.fixture
def static_game_data(mock_data_root):
    return StaticGameData(mock_data_root)


def test_load_data_not_empty(static_game_data):
    """Verify that data is loaded."""
    weapons = static_game_data.list_weapons()
    stats = static_game_data.list_stats()
    types = static_game_data.list_weapon_types()

    assert len(weapons) == 1
    assert len(stats) == 2
    assert len(types) == 1


def test_get_weapon(static_game_data):
    target = static_game_data.get_weapon("weapon_1")
    assert target is not None
    assert target.name == "Weapon 1"
    assert target.weapon_id == "weapon_1"

    assert static_game_data.get_weapon("non_existent_id") is None


def test_get_stat(static_game_data):
    target = static_game_data.get_stat("stat_a")
    assert target is not None
    assert target.name == "Stat A"

    assert static_game_data.get_stat("non_existent_id") is None


def test_get_weapon_type(static_game_data):
    target = static_game_data.get_weapon_type(WeaponTypeId.SWORD)
    assert target is not None
    assert target.name == "Sword"

    assert static_game_data.get_weapon_type("non_existent") is None


def test_get_weapons_by_type(static_game_data):
    type_weapons = static_game_data.get_weapons_by_type(WeaponTypeId.SWORD)
    assert len(type_weapons) == 1
    assert type_weapons[0].weapon_id == "weapon_1"


def test_find_weapons_by_stats(static_game_data):
    # Exact match
    found = static_game_data.find_weapons_by_stats("stat_a", "stat_b", None)
    assert "weapon_1" in found

    # Partial search (mapped to exact match in StaticGameData)
    found = static_game_data.find_weapons_by_stats(attr="stat_a")
    assert "weapon_1" not in found  # Because weapon_1 has stat2_id="stat_b"

    # Match none
    found = static_game_data.find_weapons_by_stats(attr="invalid_attr")
    assert len(found) == 0


def test_get_rarity_color(static_game_data):
    # rarity 4 should be #9452FA
    color = static_game_data.get_rarity_color(4)
    assert color == "#9452FA"

    # Fallback
    assert static_game_data.get_rarity_color(99) == "#FFFFFF"
