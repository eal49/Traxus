"""
Server-side credential store.

The store is a JSON file mapping usernames to bcrypt hashes:
  { "alice": "$2b$12$...", "bob": "$2b$12$..." }

All functions are pure and stateless — no global mutable state.
"""
from __future__ import annotations

import json
from pathlib import Path

import bcrypt


def load(path: str | None) -> dict | None:
    """Load the credentials file. Returns None if path is None or the file is absent."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def verify(store: dict, username: str, password: str) -> bool:
    """Return True iff username exists in store and password matches its bcrypt hash."""
    stored_hash = store.get(username)
    if stored_hash is None:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def add_user(path: str, username: str, password: str) -> None:
    """Hash password and write/overwrite the entry for username in the credentials file."""
    hashed = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    p = Path(path)
    try:
        with open(p, encoding="utf-8") as f:
            store = json.load(f)
    except FileNotFoundError:
        store = {}

    store[username] = hashed

    # Write via a sibling temp file to avoid partial-write corruption.
    tmp = p.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    tmp.replace(p)
