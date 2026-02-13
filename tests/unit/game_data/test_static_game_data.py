import pytest

from endfield_essence_recognizer.game_data.static_game_data import StaticGameData


@pytest.fixture
def static_game_data():
    # The CI environment will hopefully contain all the data we
    # need, so we do not mock data loading here.
    return StaticGameData()


def test_load_data_not_empty(static_game_data):
    """Verify that data is loaded (assuming tests run in environment with data)."""
    weapons = static_game_data.list_weapons()
    gems = static_game_data.list_gems()
    types = static_game_data.list_weapon_types()

    assert len(weapons) > 0
    assert len(gems) > 0
    assert len(types) > 0


def test_get_weapon(static_game_data):
    weapons = static_game_data.list_weapons()
    if weapons:
        target = weapons[0]
        assert static_game_data.get_weapon(target.weapon_id) == target

    assert static_game_data.get_weapon("non_existent_id") is None


def test_get_gem(static_game_data):
    gems = static_game_data.list_gems()
    if gems:
        target = gems[0]
        assert static_game_data.get_gem(target.gem_id) == target

    assert static_game_data.get_gem("non_existent_id") is None


def test_get_weapon_type(static_game_data):
    types = static_game_data.list_weapon_types()
    if types:
        target = types[0]
        assert static_game_data.get_weapon_type(target.weapon_type_id) == target

    assert static_game_data.get_weapon_type(9999) is None


def test_get_weapons_by_type(static_game_data):
    weapons = static_game_data.list_weapons()
    if weapons:
        target_type = weapons[0].weapon_type
        type_weapons = static_game_data.get_weapons_by_type(target_type)
        assert len(type_weapons) > 0
        assert all(w.weapon_type == target_type for w in type_weapons)


def test_find_weapons_by_stats(static_game_data):
    weapons = static_game_data.list_weapons()
    if weapons:
        w = weapons[0]
        # Exact match of all 3 gems
        found = static_game_data.find_weapons_by_stats(w.gem1_id, w.gem2_id, w.gem3_id)
        assert w.weapon_id in found

        # If we only search for attr, it should only return weapons where sec and skill are None
        found = static_game_data.find_weapons_by_stats(attr=w.gem1_id)
        if w.gem2_id is not None or w.gem3_id is not None:
            assert w.weapon_id not in found
        else:
            assert w.weapon_id in found

        # Match none
        found = static_game_data.find_weapons_by_stats(attr="invalid_attr")
        assert len(found) == 0


def test_get_rarity_color(static_game_data):
    # rarity 4 should be #9452FA
    color = static_game_data.get_rarity_color(4)
    assert color == "#9452FA"

    # Fallback
    assert static_game_data.get_rarity_color(99) == "#FFFFFF"
