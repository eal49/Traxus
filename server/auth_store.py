"""
Server-side credential store.

The store is a JSON file mapping usernames to rich entry objects:
  { "alice": { "hash": "$2b$12$...", "must_change": false } }

Old flat format ( { "alice": "$2b$12$..." } ) is auto-migrated on load.

All functions are pure and stateless — no global mutable state.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    import bcrypt
except ImportError:  # pragma: no cover
    bcrypt = None  # type: ignore[assignment]

_MIN_PASSWORD_LEN = 10


def _normalise(entry: dict | str) -> dict:
    """Return a rich entry dict, migrating a flat hash string if needed."""
    if isinstance(entry, str):
        return {"hash": entry, "must_change": False}
    return entry


def load(path: str | None) -> dict | None:
    """Load the credentials file. Returns None if path is None or the file is absent.

    Flat entries ({ username: hash_string }) are transparently normalised to
    { username: { "hash": ..., "must_change": false } } in memory; the file is
    not rewritten during load.
    """
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return {k: _normalise(v) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def verify(store: dict, username: str, password: str) -> bool:
    """Return True iff username exists in store and password matches its bcrypt hash."""
    if bcrypt is None:
        raise ImportError("bcrypt is required for password auth: pip install bcrypt>=4.0")
    entry = store.get(username)
    if entry is None:
        return False
    stored_hash = _normalise(entry)["hash"]
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def get_must_change(store: dict, username: str) -> bool:
    """Return the must_change flag for username, or False if not found."""
    entry = store.get(username)
    if entry is None:
        return False
    return bool(_normalise(entry).get("must_change", False))


def add_user(path: str, username: str, password: str, must_change: bool = True) -> None:
    """Hash password and write/overwrite the entry for username in the credentials file."""
    if bcrypt is None:
        raise ImportError("bcrypt is required for password auth: pip install bcrypt>=4.0")
    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    p = Path(path)
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}

    raw[username] = {"hash": hashed, "must_change": must_change}

    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    tmp.replace(p)


def change_password(
    path: str,
    username: str,
    old_password: str,
    new_password: str,
) -> str | None:
    """Attempt to change the password for username.

    Returns None on success, or a PasswordChangeError reason string on failure.
    Enforces: old password correct, new ≥ 10 chars, new ≠ old.
    On success writes the new hash atomically and clears must_change.
    """
    if bcrypt is None:
        raise ImportError("bcrypt is required for password auth: pip install bcrypt>=4.0")

    store = load(path)
    if store is None:
        return "auth_disabled"

    if not verify(store, username, old_password):
        return "wrong_password"

    if len(new_password) < _MIN_PASSWORD_LEN:
        return "too_short"

    if old_password == new_password:
        return "same_password"

    new_hash = bcrypt.hashpw(
        new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    p = Path(path)
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        raw = {}

    raw[username] = {"hash": new_hash, "must_change": False}

    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2)
    tmp.replace(p)

    return None
