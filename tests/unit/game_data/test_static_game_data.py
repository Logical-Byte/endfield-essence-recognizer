import json

import pytest

from endfield_essence_recognizer.game_data.static_game_data import StaticGameData


@pytest.fixture
def mock_data_root(tmp_path):
    # Weapons
    weapon_data = {
        "weapon_1": {
            "weapon_id": "weapon_1",
            "name": "Weapon 1",
            "weapon_type": 1,
            "rarity": 4,
            "icon_id": "icon_1",
            "gem1_id": "gem_a",
            "gem2_id": "gem_b",
            "gem3_id": None,
        }
    }
    (tmp_path / "Weapon.json").write_text(json.dumps(weapon_data), encoding="utf-8")

    # Gems
    gem_data = {
        "gem_a": {"gem_id": "gem_a", "name": "Gem A", "type": "ATTRIBUTE"},
        "gem_b": {"gem_id": "gem_b", "name": "Gem B", "type": "SECONDARY"},
    }
    (tmp_path / "EssenceGem.json").write_text(json.dumps(gem_data), encoding="utf-8")

    # Weapon Types
    type_data = {
        "1": {
            "weapon_type_id": 1,
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
    gems = static_game_data.list_gems()
    types = static_game_data.list_weapon_types()

    assert len(weapons) == 1
    assert len(gems) == 2
    assert len(types) == 1


def test_get_weapon(static_game_data):
    target = static_game_data.get_weapon("weapon_1")
    assert target is not None
    assert target.name == "Weapon 1"
    assert target.weapon_id == "weapon_1"

    assert static_game_data.get_weapon("non_existent_id") is None


def test_get_gem(static_game_data):
    target = static_game_data.get_gem("gem_a")
    assert target is not None
    assert target.name == "Gem A"

    assert static_game_data.get_gem("non_existent_id") is None


def test_get_weapon_type(static_game_data):
    target = static_game_data.get_weapon_type(1)
    assert target is not None
    assert target.name == "Sword"

    assert static_game_data.get_weapon_type(9999) is None


def test_get_weapons_by_type(static_game_data):
    type_weapons = static_game_data.get_weapons_by_type(1)
    assert len(type_weapons) == 1
    assert type_weapons[0].weapon_id == "weapon_1"


def test_find_weapons_by_stats(static_game_data):
    # Exact match
    found = static_game_data.find_weapons_by_stats("gem_a", "gem_b", None)
    assert "weapon_1" in found

    # Partial search (mapped to exact match in StaticGameData)
    found = static_game_data.find_weapons_by_stats(attr="gem_a")
    assert "weapon_1" not in found  # Because weapon_1 has gem2_id="gem_b"

    # Match none
    found = static_game_data.find_weapons_by_stats(attr="invalid_attr")
    assert len(found) == 0


def test_get_rarity_color(static_game_data):
    # rarity 4 should be #9452FA
    color = static_game_data.get_rarity_color(4)
    assert color == "#9452FA"

    # Fallback
    assert static_game_data.get_rarity_color(99) == "#FFFFFF"
