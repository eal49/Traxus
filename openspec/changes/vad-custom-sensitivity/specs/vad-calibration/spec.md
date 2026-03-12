## ADDED Requirements

### Requirement: VAD calibration screen displays live audio energy
The `VadCalibrationScreen` modal SHALL open the microphone and render a continuously updated ASCII bar chart of incoming RMS energy so the user can see their voice level in real time.

#### Scenario: Screen opens microphone on mount
- **WHEN** the `VadCalibrationScreen` is mounted
- **THEN** the microphone input stream SHALL open and begin sampling audio at 16 000 Hz

#### Scenario: Bar chart updates in real time
- **WHEN** the calibration screen is open and the user speaks
- **THEN** the energy bar SHALL grow and shrink in response to voice level, updating at least every 100ms

#### Scenario: Threshold marker is visible
- **WHEN** the calibration screen is open
- **THEN** a horizontal threshold line SHALL be visible within the bar chart display showing the current threshold level

#### Scenario: Screen closes microphone on dismiss
- **WHEN** the calibration screen is dismissed (Enter or Escape)
- **THEN** the microphone input stream SHALL be closed

### Requirement: User adjusts threshold via keyboard
The calibration screen SHALL allow the user to move the threshold up and down using keyboard keys, with the chart updating immediately.

#### Scenario: Up arrow raises threshold
- **WHEN** the calibration screen is open and the user presses the Up arrow key
- **THEN** the threshold value SHALL increase by a small step and the threshold marker SHALL move up in the chart

#### Scenario: Down arrow lowers threshold
- **WHEN** the calibration screen is open and the user presses the Down arrow key
- **THEN** the threshold value SHALL decrease by a small step (minimum 1) and the threshold marker SHALL move down in the chart

#### Scenario: Page Up raises threshold by large step
- **WHEN** the calibration screen is open and the user presses Page Up
- **THEN** the threshold value SHALL increase by a large step

#### Scenario: Page Down lowers threshold by large step
- **WHEN** the calibration screen is open and the user presses Page Down
- **THEN** the threshold value SHALL decrease by a large step (minimum 1)

#### Scenario: Threshold cannot go below 1
- **WHEN** the user attempts to lower the threshold below 1
- **THEN** the threshold SHALL remain at 1 and not decrease further

### Requirement: Calibration result is saved on confirmation
Pressing Enter on the calibration screen SHALL save the current threshold as `vad_custom_threshold` in settings and dismiss the screen.

#### Scenario: Enter saves threshold
- **WHEN** the calibration screen is open and the user presses Enter
- **THEN** the current threshold value SHALL be saved to `~/.config/traxus/settings.json` as `vad_custom_threshold`
- **THEN** the screen SHALL dismiss and the settings menu SHALL be restored

#### Scenario: Escape discards threshold change
- **WHEN** the calibration screen is open and the user presses Escape
- **THEN** the previously saved `vad_custom_threshold` SHALL remain unchanged
- **THEN** the screen SHALL dismiss and the settings menu SHALL be restored
