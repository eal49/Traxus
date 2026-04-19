"""
Settings persistence for Traxus.

Settings are stored at ~/.config/traxus/settings.json.
Missing or malformed files silently fall back to defaults.

Primary deployment target is Linux; ~/.config/traxus/ is used on all platforms
for simplicity (no platformdirs dependency).
"""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "traxus"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS: dict = {
    "ptt_key": "f9",
    "ptt_mode": "toggle",
    "vad_sensitivity": "high",
    "vad_custom_threshold": 50.0,
    "noise_suppression": True,
    "last_server": "",
    "last_username": "",
    "nick_color": "",
    "jitter_buffer_frames": 5,
    "stun_server": "stun:stun.l.google.com:19302",
}


def load_settings() -> dict:
    """Load settings from disk. Returns defaults on missing or malformed file."""
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(_DEFAULTS)
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def save_settings(data: dict) -> None:
    """Persist settings to disk. Creates the config directory if needed."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
