## Purpose
Persist the last-used server URL and username across sessions so returning users reach the chat screen faster.
## Requirements
### Requirement: Login screen pre-fills server URL from saved settings
On mount, the `LoginScreen` SHALL read `last_server` from `~/.config/traxus/settings.json` and pre-fill the server URL input with that value.

#### Scenario: Previously used server URL appears in the field
- **WHEN** `last_server` is set in settings and the login screen opens
- **THEN** the server URL `Input` SHALL contain that value

#### Scenario: Empty field when no previous server saved
- **WHEN** `last_server` is absent or empty in settings
- **THEN** the server URL `Input` SHALL be empty (existing behaviour)

### Requirement: Login screen pre-fills username from saved settings
On mount, the `LoginScreen` SHALL read `last_username` from `~/.config/traxus/settings.json` and pre-fill the username input with that value.

#### Scenario: Previously used username appears in the field
- **WHEN** `last_username` is set in settings and the login screen opens
- **THEN** the username `Input` SHALL contain that value

#### Scenario: Empty field when no previous username saved
- **WHEN** `last_username` is absent or empty in settings
- **THEN** the username `Input` SHALL be empty (existing behaviour)

### Requirement: Successful connect persists server URL and username
When the user successfully connects (auth acknowledged), the client SHALL write the server URL and username back to settings so they are available on next launch.

#### Scenario: Values saved after connect
- **WHEN** the user fills in a server URL and username and presses Connect
- **THEN** `last_server` and `last_username` SHALL be written to settings before the ChatScreen appears

#### Scenario: No auto-connect on launch
- **WHEN** the login screen opens with pre-filled values
- **THEN** the client SHALL NOT attempt to connect automatically — the user must press Connect

### Requirement: Settings defaults include last_server and last_username
`client/settings.py` `_DEFAULTS` SHALL include `last_server: ""` and `last_username: ""` so existing settings files without these keys fall back gracefully.

#### Scenario: Missing keys fall back to empty string
- **WHEN** `settings.json` exists but does not contain `last_server` or `last_username`
- **THEN** `load_settings()` SHALL return `""` for both keys without error

### Requirement: LoginScreen displays a Password input field
The `LoginScreen` SHALL include a Password `Input` widget with `password=True` (masked characters), positioned below the username field. The field SHALL be optional — leaving it blank is valid for connecting to no-auth servers.

#### Scenario: Password field rendered on login screen
- **WHEN** the login screen opens
- **THEN** a masked password input SHALL be visible below the username field

#### Scenario: Blank password field connects to no-auth server
- **WHEN** the user leaves the password field empty and presses Connect
- **THEN** the client SHALL attempt connection without including a `password` key in the `auth` message

#### Scenario: Filled password field included in auth message
- **WHEN** the user enters a password and presses Connect
- **THEN** the client SHALL include `"password": "<value>"` in the `auth` C2S message

### Requirement: Password is never persisted to settings
The client SHALL NOT write the contents of the password field to `settings.json`, either on connect or at any other time. The field SHALL always start empty on each launch.

#### Scenario: Password absent from settings after connect
- **WHEN** the user connects successfully with a password
- **THEN** `~/.traxus/settings.json` SHALL NOT contain a `password` key

#### Scenario: Password field empty on relaunch
- **WHEN** the application is relaunched after a previous session that used a password
- **THEN** the password field SHALL be empty (server URL and username may be pre-filled, but not password)

