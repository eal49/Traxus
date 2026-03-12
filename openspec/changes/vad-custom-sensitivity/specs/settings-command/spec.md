## MODIFIED Requirements

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
