## ADDED Requirements

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
