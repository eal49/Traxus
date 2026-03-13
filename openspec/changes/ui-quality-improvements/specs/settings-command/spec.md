## ADDED Requirements

### Requirement: Settings file persists last used server URL and username
`~/.config/traxus/settings.json` SHALL store `last_server` (string) and `last_username` (string) keys alongside the existing PTT and VAD settings.

#### Scenario: last_server key is written on connect
- **WHEN** the user successfully connects to a server
- **THEN** `last_server` SHALL be written to the settings file with the URL that was used

#### Scenario: last_username key is written on connect
- **WHEN** the user successfully connects to a server
- **THEN** `last_username` SHALL be written to the settings file with the username that was used

#### Scenario: Default value is empty string
- **WHEN** no previous connection has been made and settings are loaded
- **THEN** both `last_server` and `last_username` SHALL default to `""`
