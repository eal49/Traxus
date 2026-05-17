## Why

Accounts are created by an admin with a temporary password the user must trust was communicated securely. There is currently no way for a user to replace that credential with one only they know, and no mechanism to enforce that they do so.

## What Changes

- `users.json` store format extended: each entry becomes `{ "hash": "...", "must_change": bool }` (auto-migrates old flat `{ username: hash }` files on read)
- `adduser.py` gains `--temp` / `--permanent` flag; `--temp` (must_change: true) is now the **default**
- New C2S message `change_password` — authenticated client sends old + new password
- New S2C messages `password_changed` (success) and `password_change_error` (failure with reason)
- `auth_ok` gains optional `must_change_password: true` field when flag is set
- Status bar shows a persistent nudge when `must_change_password` is active
- New `/passwd` slash command opens a `ChangePasswordScreen` modal
- `/passwd` is disabled (shows an error) when the server has no auth store

## Capabilities

### New Capabilities

- `user-password-change`: Client-initiated password change via `/passwd` command — current/new/confirm fields, server-side validation (min 10 chars, reject same-as-old, verify current), clears `must_change` flag on success
- `password-renewal-nudge`: Soft-nudge UX when `must_change_password` is true — status bar suffix and dismissal after successful change

### Modified Capabilities

- `server-auth`: Store format changes (rich object vs flat string); `auth_ok` gains `must_change_password` field; `adduser` gains `--temp`/`--permanent` flags with `--temp` as default
- `websocket-protocol-reference`: Two new C2S and two new S2C message types
- `slash-command-reference`: New `/passwd` command entry
- `settings-command`: No requirement change — `/passwd` is a separate command, not a settings panel item

## Impact

- `server/auth_store.py` — `load()` migration logic, `add_user()` new signature, new `change_password()` function
- `server/adduser.py` — `--temp` / `--permanent` CLI flag
- `server/message_router.py` — new `_handle_change_password` handler; `auth_ok` payload updated
- `shared/message_types.py` — new C2S / S2C / ErrorCode constants
- `client/app.py` — handle `password_changed` / `password_change_error` server messages; update status bar nudge reactively
- `client/commands.py` — add `/passwd` to known commands
- `client/screens/` — new `ChangePasswordScreen` modal
- `client/widgets/status_bar.py` — conditional nudge rendering
- `tests/` — new test files for auth_store migration, change_password handler, ChangePasswordScreen
