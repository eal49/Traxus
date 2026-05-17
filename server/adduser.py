"""
Admin utility: add or update a user in the Traxus credentials file.

Usage:
    TRAXUS_USERS=/home/ubuntu/traxus/users.json python -m server.adduser <username>
    TRAXUS_USERS=/home/ubuntu/traxus/users.json python -m server.adduser <username> --permanent
"""
from __future__ import annotations

import getpass
import os
import sys


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    users_path = os.environ.get("TRAXUS_USERS", "").strip()
    if not users_path:
        print(
            "Error: TRAXUS_USERS is not set.\n"
            "Set it to the credentials file path, e.g.:\n"
            "  TRAXUS_USERS=/etc/traxus/users.json python -m server.adduser <username>",
            file=sys.stderr,
        )
        return 1

    args = list(argv)
    permanent = "--permanent" in args
    args = [a for a in args if a != "--permanent"]

    if not args:
        print(
            "Usage: python -m server.adduser <username> [--permanent]\n"
            "  --permanent   Set password without requiring a change on first login",
            file=sys.stderr,
        )
        return 1

    username = args[0].strip()
    if not username:
        print("Error: username cannot be empty.", file=sys.stderr)
        return 1

    must_change = not permanent

    while True:
        password = getpass.getpass(f"Password for {username!r}: ")
        if not password:
            print("Password cannot be empty. Try again.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Try again.")
            continue
        break

    from server import auth_store
    auth_store.add_user(users_path, username, password, must_change=must_change)
    flag_note = "" if must_change else " (permanent — no change required on first login)"
    print(f"User {username!r} written to {users_path}.{flag_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
