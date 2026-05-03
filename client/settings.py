"""
Settings persistence for Traxus.

Settings are stored at ~/.config/traxus/settings.json.
Missing or malformed files silently fall back to defaults.

Primary deployment target is Linux; ~/.config/traxus/ is used on all platforms
for simplicity (no platformdirs dependency).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "traxus"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_DEFAULTS: dict = {
    "ptt_key": "f9",
    "ptt_mode": "toggle",
    "vad_sensitivity": "high",
    "vad_custom_threshold": 50.0,
    "last_server": "",
    "last_username": "",
    "nick_color": "",
    "jitter_buffer_frames": 5,
    "stun_server": "stun:stun.l.google.com:19302",
    "input_device": None,
    "output_device": None,
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


# ── Command history ───────────────────────────────────────────────────────────

_HISTORY_FILE = _CONFIG_DIR / "command_history.json"
MAX_HISTORY = 200


def load_history() -> list[str]:
    """Load slash-command history from disk. Returns [] on missing or invalid file."""
    try:
        data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [e for e in data if isinstance(e, str)]
        return []
    except Exception:
        return []


def save_history(entries: list[str]) -> None:
    """Persist slash-command history atomically."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=_CONFIG_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f)
        os.replace(tmp, _HISTORY_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
