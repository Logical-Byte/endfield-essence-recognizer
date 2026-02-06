import sys
from pathlib import Path

if getattr(sys, "frozen", False) and (_MEIPASS := getattr(sys, "_MEIPASS", None)):
    _ROOT_DIR = Path(
        _MEIPASS
    ).parent.resolve()  # frozen executable root, contains the executable file
else:
    _ROOT_DIR = Path(
        __file__
    ).parent.parent.parent.parent.resolve()  # development project root


def get_root_dir() -> Path:
    """
    The root directory of the project. In development, this is the project root.
    In production (frozen by PyInstaller), this is the directory that holds the executable.
    The `logs` and `config.json` files are located in this directory. The `.env` file in this
    directory is also used for configuration in development and production.
    """
    return _ROOT_DIR


def get_config_path() -> Path:
    """Get the path to the config.json file in the root directory."""
    return get_root_dir() / "config.json"


def get_logs_dir() -> Path:
    """Get the path to the logs directory in the root directory."""
    return get_root_dir() / "logs"


def get_screenshots_dir() -> Path:
    """Get the path to the screenshots directory in the root directory."""
    return get_root_dir() / "screenshots"
