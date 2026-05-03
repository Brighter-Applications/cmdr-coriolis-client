"""Configuration management for cmdr-coriolis-client.

Stores user settings (API key, journal path) in a JSON file located in the
platform-appropriate user data directory.
"""

import json
import os
import sys

_APP_NAME = "cmdr-coriolis-client"

# Keys used in the config file
KEY_API_KEY = "api_key"
KEY_JOURNAL_PATH = "journal_path"
KEY_LAST_JOURNAL_FILE = "last_journal_file"
KEY_LAST_FILE_POSITION = "last_file_position"


def _config_dir() -> str:
    """Return the directory where the config file should be stored."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    path = os.path.join(base, _APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def config_file_path() -> str:
    """Return the full path to the config JSON file."""
    return os.path.join(_config_dir(), "config.json")


def load_config() -> dict:
    """Load and return the configuration dictionary.

    Returns an empty dict if the file does not exist or is invalid.
    """
    path = config_file_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_config(config: dict) -> None:
    """Persist *config* to disk, merging with any existing values."""
    existing = load_config()
    existing.update(config)
    path = config_file_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)


def get_api_key() -> str:
    """Return the stored API key, or an empty string if not set."""
    return load_config().get(KEY_API_KEY, "")


def set_api_key(api_key: str) -> None:
    """Store *api_key* in the config file."""
    save_config({KEY_API_KEY: api_key})


def get_journal_path() -> str:
    """Return the user-configured journal directory, or an empty string."""
    return load_config().get(KEY_JOURNAL_PATH, "")


def set_journal_path(path: str) -> None:
    """Store *path* as the journal directory in the config file."""
    save_config({KEY_JOURNAL_PATH: path})


def get_last_position() -> tuple:
    """Return (journal_filename, file_position) or ('', 0) if not set."""
    cfg = load_config()
    return cfg.get(KEY_LAST_JOURNAL_FILE, ''), cfg.get(KEY_LAST_FILE_POSITION, 0)


def set_last_position(journal_file: str, position: int) -> None:
    """Store the last successfully processed position."""
    save_config({
        KEY_LAST_JOURNAL_FILE: journal_file,
        KEY_LAST_FILE_POSITION: position,
    })
