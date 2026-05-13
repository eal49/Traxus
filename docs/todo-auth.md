# TODO: User Authentication

## Problem

Currently any username can connect to the server with no verification. Goals:

- Prevent strangers from joining without credentials
- Persistent identities (username reserved across sessions)

## Agreed approach

- Credentials stored in a **JSON file** at a path set by env var (`TRAXUS_USERS=/home/ubuntu/Traxus/users.json`)
- Passwords hashed with **bcrypt** (`bcrypt` package or `passlib`)
- Server falls back to **no auth required** if the file does not exist — preserves current behaviour for local/dev use
- Single role for now: authenticated user. Admin commands (`/kick`, `/ban`) deferred.

## Setup flow

Admin creates accounts once via a helper command (never in the codebase):

```bash
python -m server.adduser admin
# prompts for password, writes bcrypt hash to users.json
```

The systemd service file sets `TRAXUS_USERS` pointing to the file outside the repo, the same way `TRAXUS_HOST` is already set.

## Open questions

- In-memory only acceptable for accounts, or must they survive server restarts?
  - Leaning toward file-backed (JSON) so accounts persist across restarts.
- Registration flow: admin-only via `adduser` helper, or `/register` command in the client?
- Should unauthenticated connections be rejected at the WebSocket handshake, or after the `AUTH` message?
