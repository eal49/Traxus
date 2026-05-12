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
- **THEN** the menu SHALL contain an entry labelled "VAD Threshold" showing the current threshold value as an integer

#### Scenario: VAD Sensitivity item absent in non-VAD modes
- **WHEN** PTT mode is `"toggle"` or `"hold"` and the settings modal opens
- **THEN** the menu SHALL NOT contain a "VAD Threshold" entry

#### Scenario: Selecting VAD Sensitivity opens VadSensitivityScreen
- **WHEN** the user selects "VAD Threshold" from the settings menu
- **THEN** `VadSensitivityScreen` SHALL open as a modal over the settings screen

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

### Requirement: Settings modal includes a Noise Suppression toggle
When `NS_AVAILABLE` is `True`, the settings modal SHALL display a "Noise Suppression" menu entry showing the current state (On / Off). Selecting it SHALL toggle the value and save it immediately. When `NS_AVAILABLE` is `False`, the entry SHALL be absent.

#### Scenario: Noise Suppression entry present when NS available
- **WHEN** `NS_AVAILABLE` is `True` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Noise Suppression" showing the current state (On or Off)

#### Scenario: Noise Suppression entry absent when NS unavailable
- **WHEN** `NS_AVAILABLE` is `False` and the settings modal opens
- **THEN** the menu SHALL NOT contain a "Noise Suppression" entry

#### Scenario: Selecting Noise Suppression toggles the state
- **WHEN** the user selects the "Noise Suppression" entry
- **THEN** the state SHALL flip (On → Off or Off → On)
- **THEN** `AudioEngine.noise_suppression_enabled` SHALL be updated to match the new state
- **THEN** the new state SHALL be saved to `~/.config/traxus/settings.json`

### Requirement: noise_suppression setting is persisted
The `noise_suppression` boolean key in `~/.config/traxus/settings.json` SHALL be written when the user toggles the setting and read at startup to initialise `AudioEngine.noise_suppression_enabled`.

#### Scenario: Setting survives restart
- **WHEN** the user disables noise suppression and relaunches the client
- **THEN** `AudioEngine.noise_suppression_enabled` SHALL be `False` on startup

#### Scenario: Missing key uses default
- **WHEN** `~/.config/traxus/settings.json` exists but does not contain `"noise_suppression"`
- **THEN** `noise_suppression_enabled` SHALL default to `True`


### Requirement: Settings menu contains a Test Microphone entry
The settings modal SHALL include a "Test Microphone" list item that is always
visible when `AUDIO_AVAILABLE` is `True`, and hidden when it is `False`.

#### Scenario: Test Microphone item present when audio available
- **WHEN** `AUDIO_AVAILABLE` is `True` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Test Microphone"

#### Scenario: Test Microphone item absent when audio unavailable
- **WHEN** `AUDIO_AVAILABLE` is `False` and the settings modal opens
- **THEN** the menu SHALL NOT contain a "Test Microphone" entry

#### Scenario: Selecting Test Microphone opens MicTestScreen
- **WHEN** the user selects "Test Microphone" from the settings menu
- **THEN** `MicTestScreen` SHALL be pushed onto the screen stack as a modal

### Requirement: Settings modal contains a Nick Color entry
The settings modal SHALL include a "Nick Color" list item showing the current color (hex or "default"). Selecting it SHALL open `ColorPickerScreen`.

#### Scenario: Nick Color entry is present
- **WHEN** the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Nick Color" showing the current hex value or "default" if none is set

#### Scenario: Selecting Nick Color opens ColorPickerScreen
- **WHEN** the user selects "Nick Color" from the settings menu
- **THEN** `ColorPickerScreen` SHALL be pushed as a modal over the settings screen

#### Scenario: Color updates after picker closes
- **WHEN** the user confirms a color in `ColorPickerScreen` and returns to the settings screen
- **THEN** the "Nick Color" entry SHALL display the newly chosen hex value

### Requirement: Settings modal shows Input Device and Output Device items
The settings modal SHALL include entries for selecting the audio input device and output device. Both items SHALL be hidden when `AUDIO_AVAILABLE` is `False`.

#### Scenario: Input Device item is present when audio is available
- **WHEN** `AUDIO_AVAILABLE` is `True` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Input Device: System Default" (or the saved device name)

#### Scenario: Output Device item is present when audio is available
- **WHEN** `AUDIO_AVAILABLE` is `True` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Output Device: System Default" (or the saved device name)

#### Scenario: Device items are hidden when audio is unavailable
- **WHEN** `AUDIO_AVAILABLE` is `False` and the settings modal opens
- **THEN** neither Input Device nor Output Device entries SHALL be visible

#### Scenario: Selecting Input Device opens DeviceSelectScreen
- **WHEN** the user selects "Input Device" from the settings menu
- **THEN** `DeviceSelectScreen` SHALL open as a modal with `kind="input"`

#### Scenario: Selecting Output Device opens DeviceSelectScreen
- **WHEN** the user selects "Output Device" from the settings menu
- **THEN** `DeviceSelectScreen` SHALL open as a modal with `kind="output"`

#### Scenario: Device label updates after selection
- **WHEN** the user selects a device and the picker closes
- **THEN** the Settings menu item label SHALL update to reflect the new selection
