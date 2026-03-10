## ADDED Requirements

### Requirement: /settings command opens a settings modal
The client SHALL support a `/settings` slash command that opens a modal settings screen without sending any message to the server.

#### Scenario: /settings opens modal
- **WHEN** the user types `/settings` in the input bar
- **THEN** a modal settings screen SHALL appear over the chat view

#### Scenario: /settings is client-only
- **WHEN** the user types `/settings`
- **THEN** no message SHALL be sent to the server

#### Scenario: Escape closes the modal
- **WHEN** the settings modal is open and the user presses Escape
- **THEN** the modal SHALL close and the chat view SHALL be restored

### Requirement: Settings modal displays a navigable menu
The settings modal SHALL present a list of setting categories that the user can navigate and select.

#### Scenario: PTT Key item is present
- **WHEN** the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "PTT Key"

#### Scenario: Selecting PTT Key opens key capture screen
- **WHEN** the user selects "PTT Key" from the settings menu
- **THEN** a key capture screen SHALL appear prompting the user to press any key

### Requirement: PTT key is bound via key capture
The PTT key capture screen SHALL wait for the user to press any key and use that key as the new PTT binding. The binding SHALL take effect immediately.

#### Scenario: Capture screen prompts the user
- **WHEN** the PTT key capture screen is displayed
- **THEN** it SHALL show the current PTT key and a prompt instructing the user to press any key or Escape to cancel

#### Scenario: Pressing a key sets PTT immediately
- **WHEN** the user presses any key (other than Escape) on the capture screen
- **THEN** that key SHALL become the new PTT binding from that point forward, without restarting the client

#### Scenario: Escape cancels without changing binding
- **WHEN** the user presses Escape on the capture screen
- **THEN** the PTT binding SHALL remain unchanged and the screen SHALL close

#### Scenario: Default PTT key is F9
- **WHEN** no settings file exists
- **THEN** the PTT key SHALL default to F9

### Requirement: PTT key setting is persisted
The selected PTT key SHALL be saved to `~/.config/traxus/settings.json` and restored on next launch.

#### Scenario: Setting survives restart
- **WHEN** the user selects a new PTT key and relaunches the client
- **THEN** the previously selected PTT key SHALL be active on startup

#### Scenario: Missing settings file uses defaults
- **WHEN** `~/.config/traxus/settings.json` does not exist
- **THEN** the client SHALL start with PTT key F9 and create the file on first save

#### Scenario: Malformed settings file uses defaults
- **WHEN** `~/.config/traxus/settings.json` exists but contains invalid JSON
- **THEN** the client SHALL start with default settings without crashing
