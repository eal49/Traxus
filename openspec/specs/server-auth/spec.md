# server-auth Specification

## Purpose
TBD - created by archiving change auth-landing. Update Purpose after archive.
## Requirements
### Requirement: Credentials file is loaded from TRAXUS_USERS env var
When the `TRAXUS_USERS` environment variable is set, the server SHALL load a JSON credentials file from that path at startup. The file SHALL map usernames to bcrypt-hashed passwords.

#### Scenario: File loaded on startup
- **WHEN** `TRAXUS_USERS` is set to a valid path and the file contains at least one entry
- **THEN** the server SHALL load the credentials into memory before accepting connections

#### Scenario: Missing file logs a warning and starts in no-auth mode
- **WHEN** `TRAXUS_USERS` is set but the file does not exist
- **THEN** the server SHALL log a warning and start in no-auth mode (no connections rejected for missing password)

### Requirement: Server operates in no-auth mode when TRAXUS_USERS is unset
When `TRAXUS_USERS` is not set, the server SHALL NOT require a password during authentication. Existing behaviour is preserved exactly.

#### Scenario: No-auth mode accepts connection without password
- **WHEN** `TRAXUS_USERS` is unset
- **THEN** a client that sends `auth` without a `password` field SHALL be accepted

#### Scenario: No-auth mode ignores password if provided
- **WHEN** `TRAXUS_USERS` is unset
- **THEN** a client that sends `auth` with a `password` field SHALL be accepted; the password is silently ignored

### Requirement: Server verifies password when credentials are loaded
When the credentials file is loaded, the server SHALL verify the `password` field of every `auth` C2S message using bcrypt before accepting the connection.

#### Scenario: Correct password accepted
- **WHEN** `TRAXUS_USERS` is set and the client sends `auth` with a username and correct password
- **THEN** the server SHALL respond with `auth_ok`

#### Scenario: Wrong password rejected
- **WHEN** `TRAXUS_USERS` is set and the client sends `auth` with a username and incorrect password
- **THEN** the server SHALL respond with `auth_error { "reason": "wrong_password" }`

#### Scenario: Missing password rejected
- **WHEN** `TRAXUS_USERS` is set and the client sends `auth` without a `password` field
- **THEN** the server SHALL respond with `auth_error { "reason": "wrong_password" }`

#### Scenario: Unknown username rejected
- **WHEN** `TRAXUS_USERS` is set and the client sends `auth` with a username not present in the credentials file
- **THEN** the server SHALL respond with `auth_error { "reason": "wrong_password" }` (no username enumeration)

### Requirement: Credentials file uses bcrypt hashes
The credentials file SHALL store only bcrypt-hashed passwords, never plaintext. The hash work factor SHALL be at least 10.

#### Scenario: Stored hash is bcrypt format
- **WHEN** `adduser` writes a new credential entry
- **THEN** the stored value SHALL be a valid bcrypt hash string starting with `$2b$`

### Requirement: adduser utility creates and updates accounts
The server package SHALL expose a CLI entry point `python -m server.adduser <username>` that prompts for a password, hashes it with bcrypt, and writes the entry to the credentials file at the path given by `TRAXUS_USERS`.

#### Scenario: New user added successfully
- **WHEN** `python -m server.adduser alice` is run with `TRAXUS_USERS` set to a writable path
- **THEN** the credentials file SHALL contain an entry for `alice` with a bcrypt hash

#### Scenario: Existing user password updated
- **WHEN** `python -m server.adduser alice` is run and `alice` already exists in the file
- **THEN** the existing entry SHALL be overwritten with the new hash

#### Scenario: TRAXUS_USERS not set exits with error
- **WHEN** `python -m server.adduser alice` is run without `TRAXUS_USERS` set
- **THEN** the command SHALL exit with a non-zero code and an informative error message

#### Scenario: Empty password rejected
- **WHEN** the user enters an empty password at the prompt
- **THEN** `adduser` SHALL reject it and re-prompt, not write an empty hash

### Requirement: auth_store module is unit-testable in isolation
The `server/auth_store.py` module SHALL expose `load(path)`, `verify(store, username, password)`, and `add_user(path, username, password)` as pure functions with no global state.

#### Scenario: load returns None for absent file
- **WHEN** `load(path)` is called with a path that does not exist
- **THEN** it SHALL return `None`

#### Scenario: verify returns False for unknown username
- **WHEN** `verify(store, "nobody", "pass")` is called with a store that does not contain `"nobody"`
- **THEN** it SHALL return `False`

