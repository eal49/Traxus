## 1. Shared constants

- [x] 1.1 Add `C2S.CHANGE_PASSWORD = "change_password"` to `shared/message_types.py`
- [x] 1.2 Add `S2C.PASSWORD_CHANGED = "password_changed"` and `S2C.PASSWORD_CHANGE_ERROR = "password_change_error"` to `shared/message_types.py`
- [x] 1.3 Add `PasswordChangeError.WRONG_PASSWORD`, `TOO_SHORT`, `SAME_PASSWORD`, `AUTH_DISABLED` constants to `shared/message_types.py`

## 2. auth_store — store format and new functions

- [x] 2.1 Update `auth_store.load()` to auto-migrate flat string entries to `{ "hash": ..., "must_change": false }` on read
- [x] 2.2 Update `auth_store.verify()` to read `entry["hash"]` when entry is a dict (rich format)
- [x] 2.3 Update `auth_store.add_user()` to accept a `must_change: bool = True` parameter and write the rich object format
- [x] 2.4 Add `auth_store.change_password(path, username, old_password, new_password) -> bool` that verifies old, enforces min-10-chars and same-as-old policy, hashes new, writes atomically, clears `must_change`
- [x] 2.5 Add `auth_store.get_must_change(store, username) -> bool` helper

## 3. adduser CLI

- [x] 3.1 Add `--permanent` flag to `adduser.py`; default behaviour sets `must_change=True`, `--permanent` sets `must_change=False`
- [x] 3.2 Update `adduser.py` help/usage text to document `--permanent`

## 4. MessageRouter — server-side handler

- [x] 4.1 Pass `auth_store_path: str | None` to `MessageRouter.__init__()` alongside the existing `auth_store` dict
- [x] 4.2 Update `_handle_auth()` to include `must_change_password: true` in the `auth_ok` payload when the user's `must_change` flag is set
- [x] 4.3 Add `_handle_change_password()` handler: verify old password, enforce policy, call `auth_store.change_password()`, reload store into `self._auth_store`, send `password_changed` or `password_change_error`
- [x] 4.4 Register `C2S.CHANGE_PASSWORD` in the `self._handlers` dispatch table

## 5. Client — ChangePasswordScreen

- [x] 5.1 Create `client/screens/change_password_screen.py` with three masked `Input` fields (current, new, confirm), a Save button, and a Cancel/Escape path
- [x] 5.2 On Save: validate confirm match client-side, send `change_password` message via `app.send_ws()`
- [x] 5.3 Display inline error label for client-side mismatch and server-side `password_change_error` responses

## 6. Client — app.py and status bar

- [x] 6.1 Add `_must_change_password: reactive[bool]` to `TraxusApp`; set it from `auth_ok` payload
- [x] 6.2 Handle `S2C.PASSWORD_CHANGED` in `on_traxus_app_server_message`: clear `_must_change_password`, dismiss `ChangePasswordScreen` if open
- [x] 6.3 Handle `S2C.PASSWORD_CHANGE_ERROR` in `on_traxus_app_server_message`: forward the reason to `ChangePasswordScreen` for inline display
- [x] 6.4 Add `_server_has_auth: bool` flag set from login flow (True when the user was asked for a password / auth was active); pass to commands
- [x] 6.5 Update `_execute_command()` to handle `/passwd`: check `_server_has_auth`, push `ChangePasswordScreen` or show error

## 7. Client — commands and status bar

- [x] 7.1 Add `passwd` to `KNOWN_COMMANDS` and `HELP_TEXT` in `client/commands.py`
- [x] 7.2 Update `StatusBar` to append `⚠ /passwd` suffix when `_must_change_password` is True

## 8. Tests

- [x] 8.1 Add `tests/test_auth_store_change.py`: migration of flat entries, `change_password()` success, wrong-old, too-short, same-as-old cases
- [x] 8.2 Add tests for `adduser.py` `--permanent` flag
- [x] 8.3 Add `MessageRouter` tests: `change_password` success, each error reason, no-auth-store rejection, `auth_ok` includes `must_change_password`
- [x] 8.4 Add `tests/test_change_password_screen.py`: mismatch shows error, Escape cancels, success clears nudge
- [x] 8.5 Add status bar nudge tests: nudge present when `_must_change_password` True, cleared on `password_changed`

## 9. Documentation

- [x] 9.1 Add `change_password`, `password_changed`, `password_change_error` entries to `docs/protocol.md`
- [x] 9.2 Add `/passwd` entry to `docs/commands.md`
- [x] 9.3 Update `docs/user-guide.md` section 6 (Settings) or add a new subsection documenting `/passwd` and the status bar nudge
- [x] 9.4 Update `README.md` slash-command table to include `/passwd`
