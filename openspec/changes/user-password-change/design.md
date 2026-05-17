## Context

The existing auth system stores credentials as a flat JSON map of `username → bcrypt_hash`. The server loads this once at startup and passes it as an immutable dict to `MessageRouter`. There is no mechanism for in-session credential mutation.

`adduser.py` is the sole write path, run by an admin on the server. The client has no way to initiate a password change, and there is no per-account metadata beyond the hash.

## Goals / Non-Goals

**Goals:**
- Let an authenticated client change their own password via `/passwd`
- Persist the change to `users.json` atomically on the server
- Enforce a minimum password length (10 chars) and reject same-as-old
- Add a `must_change` flag per account, defaulting to `true` for new accounts
- Surface a status bar nudge to users whose `must_change` flag is set
- Auto-migrate old flat `{ username: hash }` files transparently

**Non-Goals:**
- Password reset without knowing the old password (no "forgot password" flow)
- Admin-initiated remote password invalidation over the WebSocket
- Password complexity rules beyond minimum length
- Session invalidation of other connected clients when a password changes
- Email or out-of-band notification

## Decisions

### 1. Store format: rich per-user object

**Decision:** Change `users.json` entries from `"alice": "$2b$12$..."` to `"alice": { "hash": "$2b$12$...", "must_change": bool }`. Auto-migrate old flat entries on `load()`.

**Alternatives considered:**
- *Sentinel prefix* (`"TEMP:$2b$12$..."`): no format change but fragile — the prefix could collide with unexpected hash strings and it embeds semantics in what should be opaque data.
- *Parallel top-level key* (`"__must_change__": ["alice"]`): backwards-compatible but splits per-user state across two locations; harder to reason about and extend later.

**Rationale:** The rich object is the only shape that scales cleanly if we ever add more per-account metadata (expiry, role, last-changed timestamp). The migration is a one-liner in `load()`.

### 2. `auth_store` stays stateless; server re-reads file per change

**Decision:** `auth_store` functions remain pure (no global state). `MessageRouter` holds the loaded store dict in `self._auth_store`. On a successful `change_password`, the handler calls `auth_store.change_password(path, ...)` (writes file) then reloads and replaces `self._auth_store`.

**Alternatives considered:**
- *Mutate the in-memory dict in place*: simpler, but if the server crashes before the next write the in-memory state diverges from disk. The reload-after-write keeps them in sync.
- *Hot-reload via inotify/watchdog*: overkill for this scale; adds an OS-specific dependency.

**Rationale:** File is the source of truth. The extra `load()` on each successful change is negligible (small JSON file).

### 3. `--temp` is the default for `adduser.py`

**Decision:** `adduser.py` sets `must_change: true` by default. Pass `--permanent` to skip the flag.

**Rationale:** Safer default — admin must explicitly opt out of enforced renewal. Matches the principle of least surprise: a freshly provisioned account should always prompt a password change.

### 4. Soft nudge, not hard gate

**Decision:** When `auth_ok` carries `must_change_password: true`, the client adds a suffix to the status bar (`⚠ /passwd`) but does not block access to chat or voice.

**Alternatives considered:**
- *Hard gate (ChangePasswordScreen before ChatScreen)*: more secure, but disruptive — the user cannot even read a message before being forced to act. Inappropriate for a chat tool where "I'll do it later" is a reasonable stance.

**Rationale:** Traxus is a self-hosted tool used by people who know each other. The nudge is sufficient to prompt action without being punitive.

### 5. Server re-verifies old password even for authenticated clients

**Decision:** `change_password` handler always calls `auth_store.verify(old_password)` even though the client is already authenticated.

**Rationale:** Prevents "grabbed unlocked terminal" attacks — someone who hijacks an active session cannot silently change the password without knowing the current one.

### 6. `users_path` passed to `MessageRouter` for write access

**Decision:** `MessageRouter.__init__` already receives the loaded `auth_store` dict. It will also receive `auth_store_path: str | None` so the change-password handler knows where to write.

**Alternatives considered:**
- *Pass a write callback*: cleaner inversion of control but adds indirection with no real benefit at this scale.

## Risks / Trade-offs

- **Concurrent writes**: if two clients change their password simultaneously, the second `load → modify → write` cycle could overwrite the first. Mitigation: the atomic temp-file replace in `add_user` / `change_password` is the last write and wins; for a self-hosted tool with a handful of users this race is acceptable. A file lock could be added later if needed.
- **In-memory dict goes stale**: after a password change the in-memory `self._auth_store` is reloaded, but other concurrent `_handle_auth` calls in flight at that exact moment may still use the old dict. Mitigation: Python's GIL makes dict replacement atomic at the reference level; at worst a concurrent login sees the old hash for one request.
- **No session invalidation**: if Alice changes her password while Bob is using her account on another terminal, Bob's session is unaffected. Non-goal for now; could be addressed by adding a `session_token` to `auth_ok` in a future change.

## Migration Plan

1. Deploy new server code — `load()` auto-migrates flat entries to rich objects on next read; no manual file conversion needed.
2. Existing clients connecting to the updated server see no change: `auth_ok` gains `must_change_password: false` (or absent) for legacy accounts.
3. New accounts created with `adduser.py` after the update get `must_change: true` by default.
4. Rollback: revert server code; old flat `users.json` entries still work; new rich entries will cause a `KeyError` on the old `verify()`. Pre-rollback, flatten the file with a one-liner: `python -c "import json,sys; d=json.load(open(sys.argv[1])); [d.update({k: v['hash'] if isinstance(v,dict) else v}) for k,v in list(d.items())]; json.dump(d,open(sys.argv[1],'w'),indent=2)" users.json`

## Open Questions

- Should a successful `change_password` also send an updated `auth_ok` (to refresh `must_change_password` to false on the client), or is a dedicated `password_changed` message sufficient? Current design uses `password_changed`; the client clears the nudge on receipt.
