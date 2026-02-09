from pathlib import Path

from endfield_essence_recognizer.core.path import get_config_path, get_screenshots_dir


def get_config_path_dep() -> Path:
    """
    The dependency to get the config path.
    """
    return get_config_path()


def get_screenshots_dir_dep() -> Path:
    """
    The dependency to get the screenshots directory path.
    """
    return get_screenshots_dir()
