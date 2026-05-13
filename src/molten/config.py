"""API key storage for the Moltbook API.

Keys are stored in ~/.config/molten/credentials.json by default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "molten"


def get_config_dir() -> Path:
    """Return the config directory, creating it if needed."""
    config_dir = Path(os.environ.get("MOLTEN_CONFIG_DIR", DEFAULT_CONFIG_DIR))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_credentials_file() -> Path:
    """Return the credentials file path.

    Defaults to <config_dir>/credentials.json.
    Override with MOLTEN_CREDENTIALS_FILE env var.
    """
    env_path = os.environ.get("MOLTEN_CREDENTIALS_FILE")
    if env_path:
        return Path(env_path)
    return get_config_dir() / "credentials.json"


def save_api_key(api_key: str, profile: str = "default") -> Path:
    """Save an API key for the given profile.

    Args:
        api_key: The Moltbook API key (starts with 'moltbook_sk_').
        profile: A name for this key (default: 'default').

    Returns:
        The path to the credentials file.
    """
    creds_file = get_credentials_file()
    creds_file.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if creds_file.exists():
        data = json.loads(creds_file.read_text())

    data[profile] = api_key
    creds_file.write_text(json.dumps(data, indent=2) + "\n")
    creds_file.chmod(0o600)  # owner-read/write only
    return creds_file


def load_api_key(profile: str = "default") -> str | None:
    """Load an API key for the given profile.

    Args:
        profile: The profile name to load (default: 'default').

    Returns:
        The API key, or None if not found.
    """
    creds_file = get_credentials_file()
    if not creds_file.exists():
        return None
    data = json.loads(creds_file.read_text())
    return data.get(profile)


def list_profiles() -> list[str]:
    """List all stored API key profiles."""
    creds_file = get_credentials_file()
    if not creds_file.exists():
        return []
    return list(json.loads(creds_file.read_text()).keys())
