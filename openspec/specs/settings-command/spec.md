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

#### Scenario: PTT Mode item is present
- **WHEN** the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "PTT Mode" showing the current mode (Toggle, Hold, or VAD)

#### Scenario: Selecting PTT Mode cycles the mode
- **WHEN** the user selects "PTT Mode" from the settings menu
- **THEN** the mode SHALL cycle Toggle → Hold → VAD → Toggle and the change SHALL be saved immediately

#### Scenario: VAD Sensitivity item appears only in VAD mode
- **WHEN** PTT mode is `"vad"` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "VAD Sensitivity" showing the current level (Low / Medium / High / Very High / Custom)

#### Scenario: VAD Sensitivity item absent in non-VAD modes
- **WHEN** PTT mode is `"toggle"` or `"hold"` and the settings modal opens
- **THEN** the menu SHALL NOT contain a "VAD Sensitivity" entry

#### Scenario: Selecting VAD Sensitivity cycles the level
- **WHEN** the user selects "VAD Sensitivity" from the settings menu and the current level is not "Custom"
- **THEN** the level SHALL cycle Low → Medium → High → Very High → Custom → Low and the change SHALL be saved immediately

#### Scenario: Selecting Custom VAD Sensitivity opens calibration screen
- **WHEN** the user selects "VAD Sensitivity" and the current level is "Custom"
- **THEN** the `VadCalibrationScreen` SHALL open as a modal over the settings screen

#### Scenario: Selecting PTT Key opens key capture screen
- **WHEN** the user selects "PTT Key" from the settings menu
- **THEN** a key capture screen SHALL appear prompting the user to press any key or click a mouse button

### Requirement: PTT key is bound via key capture
The PTT key capture screen SHALL wait for the user to press any key or click any mouse button and use that input as the new PTT binding. The binding SHALL take effect immediately.

#### Scenario: Capture screen prompts the user
- **WHEN** the PTT key capture screen is displayed
- **THEN** it SHALL show the current PTT binding and a prompt instructing the user to press any key or click a mouse button, or press Escape to cancel

#### Scenario: Pressing a key sets PTT immediately
- **WHEN** the user presses any key (other than Escape) on the capture screen
- **THEN** that key SHALL become the new PTT binding from that point forward, without restarting the client

#### Scenario: Clicking a mouse button sets PTT immediately
- **WHEN** the user clicks any mouse button on the capture screen
- **THEN** that mouse button SHALL become the new PTT binding from that point forward, stored as `"mouseN"`, without restarting the client

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
