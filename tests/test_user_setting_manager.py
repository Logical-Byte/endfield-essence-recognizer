import json

import pytest
from pydantic import ValidationError

from endfield_essence_recognizer.exceptions import ConfigVersionMismatchError
from endfield_essence_recognizer.models.user_setting import UserSetting
from endfield_essence_recognizer.services.user_setting_manager import (
    UserSettingManager,
)


@pytest.fixture
def settings_file(tmp_path):
    return tmp_path / "settings.json"


@pytest.fixture
def manager(settings_file):
    return UserSettingManager(settings_file)


def test_manager_initial_state(manager, settings_file):
    """Test the initial state of the UserSettingManager."""
    assert manager._user_setting_file == settings_file
    assert isinstance(manager.get_user_setting(), UserSetting)


def test_get_user_setting_returns_copy(manager):
    """Test that get_user_setting returns a deep copy of the settings."""
    s1 = manager.get_user_setting()
    s2 = manager.get_user_setting()
    assert s1 == s2
    assert s1 is not s2


def test_load_user_setting_file_not_exists(manager, settings_file):
    """Test that loading from a non-existent file creates a default setting file."""
    assert not settings_file.exists()
    manager.load_user_setting()
    assert settings_file.exists()
    # Should be default settings
    assert manager.get_user_setting().trash_weapon_ids == []


def test_load_user_setting_valid_file(manager, settings_file):
    """Test that a valid setting file is correctly loaded into memory."""
    data = {
        "version": UserSetting._VERSION,
        "trash_weapon_ids": ["weapon_1"],
        "treasure_essence_stats": [
            {"attribute": "atk", "secondary": "crit", "skill": None}
        ],
    }
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    manager.load_user_setting()
    setting = manager.get_user_setting()
    assert setting.trash_weapon_ids == ["weapon_1"]
    assert len(setting.treasure_essence_stats) == 1
    assert setting.treasure_essence_stats[0].attribute == "atk"


def test_load_user_setting_invalid_version_backups_file(manager, settings_file):
    """Test that a file with an invalid version is backed up and replaced with defaults."""
    data = {
        "version": -1,  # Wrong version
        "trash_weapon_ids": ["old_weapon"],
    }
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    manager.load_user_setting()

    # Check backup exists
    backup_file = settings_file.with_suffix(".backup.json")
    assert backup_file.exists()
    assert json.loads(backup_file.read_text(encoding="utf-8"))["trash_weapon_ids"] == [
        "old_weapon"
    ]

    # Current setting should be default
    assert manager.get_user_setting().trash_weapon_ids == []
    # New file should be saved with defaults
    assert settings_file.exists()
    assert (
        json.loads(settings_file.read_text(encoding="utf-8"))["version"]
        == UserSetting._VERSION
    )


def test_load_user_setting_corrupt_json_backups_file(manager, settings_file):
    """Test that a corrupt JSON file is backed up and replaced with defaults."""
    settings_file.write_text("not a json", encoding="utf-8")

    manager.load_user_setting()

    backup_file = settings_file.with_suffix(".backup.json")
    assert backup_file.exists()
    assert backup_file.read_text(encoding="utf-8") == "not a json"

    assert manager.get_user_setting().version == UserSetting._VERSION


def test_update_from_dict_version_mismatch(manager):
    """Test that update_from_dict raises ConfigVersionMismatchError on version mismatch."""
    data = {"version": -1, "trash_weapon_ids": ["test"]}
    with pytest.raises(ConfigVersionMismatchError) as excinfo:
        manager.update_from_dict(data)
    assert excinfo.value.expected == UserSetting._VERSION
    assert excinfo.value.got == -1


def test_update_from_user_setting_version_mismatch(manager):
    """Test that update_from_user_setting raises ConfigVersionMismatchError on version mismatch."""
    other = UserSetting()
    other.version = -1
    with pytest.raises(ConfigVersionMismatchError) as excinfo:
        manager.update_from_user_setting(other)
    assert excinfo.value.expected == UserSetting._VERSION
    assert excinfo.value.got == -1


def test_save_user_setting(manager, settings_file):
    """Test that save_user_setting correctly persists in-memory settings to disk."""
    # Accessing private member for test setup
    setting = manager._user_setting
    setting.trash_weapon_ids = ["test_save"]
    manager.save_user_setting()

    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["trash_weapon_ids"] == ["test_save"]


def test_update_from_dict(manager, settings_file):
    """Test that update_from_dict updates settings and saves to disk."""
    manager.update_from_dict({"trash_weapon_ids": ["dict_update"]})
    assert manager.get_user_setting().trash_weapon_ids == ["dict_update"]
    assert json.loads(settings_file.read_text(encoding="utf-8"))[
        "trash_weapon_ids"
    ] == ["dict_update"]


def test_update_from_user_setting(manager, settings_file):
    """Test that update_from_user_setting updates settings and saves to disk."""
    new_setting = UserSetting(trash_weapon_ids=["model_update"])
    manager.update_from_user_setting(new_setting)
    assert manager.get_user_setting().trash_weapon_ids == ["model_update"]
    assert json.loads(settings_file.read_text(encoding="utf-8"))[
        "trash_weapon_ids"
    ] == ["model_update"]


def test_update_from_dict_invalid_data(manager):
    """Test that update_from_dict raises an exception when provided with invalid data."""
    with pytest.raises(ValidationError):
        manager.update_from_dict({"trash_weapon_ids": "not a list"})
