from pathlib import Path

from endfield_essence_recognizer.core.path import (
    get_config_path,
    get_exports_dir,
    get_root_dir,
    get_screenshots_dir,
)


def get_config_path_dep() -> Path:
    """
    The dependency to get the config path.
    """
    return get_config_path()


def get_custom_alluviums_path_dep() -> Path:
    """
    The dependency to get the custom alluviums data file path.

    It sits next to config.json, so it is user data of the installation root
    rather than of any single profile.
    """
    return get_root_dir() / "custom_alluviums.json"


def get_screenshots_dir_dep() -> Path:
    """
    The dependency to get the screenshots directory path.
    """
    return get_screenshots_dir()


def get_exports_dir_dep() -> Path:
    """
    The dependency to get the exports directory path.
    """
    return get_exports_dir()
