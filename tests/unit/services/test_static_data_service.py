import pytest

from endfield_essence_recognizer.core.path import get_root_dir
from endfield_essence_recognizer.game_data.models.v2 import (
    StatType,
)
from endfield_essence_recognizer.game_data.static_game_data import StaticGameData
from endfield_essence_recognizer.services.static_data_service import StaticDataService


@pytest.fixture
def static_game_data():
    # We can use a real one or mock it. Using real one for integration-like unit test.
    data_root = get_root_dir() / "resources" / "data" / "v2"
    return StaticGameData(data_root)


@pytest.fixture
def service(static_game_data):
    return StaticDataService(static_game_data)


def test_get_weapon_service(service):
    # This depends on data being present
    weapons = service.list_weapons().weapons
    assert len(weapons) > 0, "Weapon dataset must not be empty"
    w_id = weapons[0].id
    weapon_info = service.get_weapon(w_id)
    assert weapon_info is not None
    assert weapon_info.id == w_id
    assert weapon_info.name != ""
    assert weapon_info.icon_url.startswith("/")


def test_list_weapon_types_service(service):
    response = service.list_weapon_types()
    assert len(response.weapon_types) > 0
    for wt in response.weapon_types:
        assert wt.id != ""
        assert wt.name != ""
        assert wt.icon_url.startswith("/")
        # Check if weapon IDs match
        for w_id in wt.weapon_ids:
            assert service.get_weapon(w_id) is not None


def test_get_rarity_colors_service(service):
    response = service.get_rarity_colors()
    assert len(response.colors) >= 6
    assert response.colors[4].upper() == "#9452FA"


def test_get_matrix_icons_service(service):
    response = service.get_matrix_icons()
    assert response.essence_bg.endswith("item_gem_rarity_5.png")
    assert response.default_icon.endswith("icon_wpngem_00.png")
    assert len(response.skills) > 0
    for skill_id, icon_url in response.skills.items():
        assert icon_url.startswith("/")
        assert skill_id.startswith("gst_passive_") or skill_id.startswith(
            "weapon.stat.gst_passive_"
        )


def test_get_essence_service(service):
    essences = service.list_essences().items
    assert len(essences) > 0, "Essence dataset must not be empty"
    e_id = essences[0].id
    essence_info = service.get_essence(e_id)
    assert essence_info is not None
    assert essence_info.id == e_id
    assert essence_info.name != ""
    assert essence_info.type in [
        StatType.ATTRIBUTE,
        StatType.SECONDARY,
        StatType.SKILL,
    ]
