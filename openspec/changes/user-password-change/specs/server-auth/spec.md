## ADDED Requirements

### Requirement: Credentials file uses rich per-user objects
Each entry in the credentials file SHALL be a JSON object with `hash` and `must_change` fields. The server SHALL transparently auto-migrate old flat entries (`"username": "$2b$12$..."`) to the rich format on first read.

#### Scenario: New entries written in rich format
- **WHEN** `add_user()` writes a new credential
- **THEN** the entry SHALL be `{ "hash": "$2b$12$...", "must_change": <bool> }`

#### Scenario: Old flat entries are migrated on load
- **WHEN** `load()` reads a file where an entry is a plain string (old format)
- **THEN** it SHALL treat it as `{ "hash": <string>, "must_change": false }` without modifying the file

### Requirement: adduser defaults to must_change true
`python -m server.adduser <username>` SHALL set `must_change: true` by default. Passing `--permanent` SHALL set `must_change: false`.

#### Scenario: Default new user has must_change true
- **WHEN** `python -m server.adduser alice` is run without flags
- **THEN** the entry for `alice` SHALL have `must_change: true`

#### Scenario: --permanent flag disables forced renewal
- **WHEN** `python -m server.adduser alice --permanent` is run
- **THEN** the entry for `alice` SHALL have `must_change: false`

### Requirement: auth_ok includes must_change_password field in auth mode
When the server is running in auth mode and the user's `must_change` flag is set, the `auth_ok` response SHALL include `must_change_password: true`.

#### Scenario: must_change_password true sent when flag is set
- **WHEN** the server authenticates a user whose entry has `must_change: true`
- **THEN** `auth_ok` SHALL include `"must_change_password": true`

#### Scenario: must_change_password absent or false when flag is not set
- **WHEN** the server authenticates a user whose entry has `must_change: false`
- **THEN** `auth_ok` SHALL NOT include `must_change_password: true`

### Requirement: auth_store exposes change_password function
`server/auth_store.py` SHALL expose a `change_password(path, username, old_password, new_password)` function that verifies the old password, enforces policy, and atomically updates the credentials file.

#### Scenario: change_password returns True on success
- **WHEN** `change_password()` is called with correct old password and a valid new password
- **THEN** it SHALL update the file, clear `must_change`, and return `True`

#### Scenario: change_password returns False for wrong old password
- **WHEN** `change_password()` is called with an incorrect old password
- **THEN** it SHALL return `False` without modifying the file

## MODIFIED Requirements

### Requirement: auth_store module is unit-testable in isolation
The `server/auth_store.py` module SHALL expose `load(path)`, `verify(store, username, password)`, `add_user(path, username, password, must_change)`, and `change_password(path, username, old_password, new_password)` as pure functions with no global state.

#### Scenario: load returns None for absent file
- **WHEN** `load(path)` is called with a path that does not exist
- **THEN** it SHALL return `None`

#### Scenario: verify returns False for unknown username
- **WHEN** `verify(store, "nobody", "pass")` is called with a store that does not contain `"nobody"`
- **THEN** it SHALL return `False`
