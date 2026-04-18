## Requirements

### Requirement: VadSensitivityScreen displays live spectrogram and level bar
The `VadSensitivityScreen` modal SHALL open the microphone and render a rolling ASCII spectrogram (frequency × time) and an RMS level bar, matching the visual output of `MicTestScreen`.

#### Scenario: Screen opens microphone on mount
- **WHEN** the `VadSensitivityScreen` is mounted
- **THEN** the microphone input stream SHALL open and begin sampling audio at 16 000 Hz

#### Scenario: Spectrogram scrolls in real time
- **WHEN** the screen is open and the user speaks
- **THEN** new frequency columns SHALL appear on the right of the spectrogram at least every 100ms, scrolling left

#### Scenario: Level bar updates in real time
- **WHEN** the screen is open and the user speaks
- **THEN** the RMS level bar SHALL grow and shrink in response to voice level

#### Scenario: Screen closes microphone on dismiss
- **WHEN** the screen is dismissed (Enter or Escape)
- **THEN** the microphone input stream SHALL be closed

### Requirement: Threshold marker shows on the level bar
The RMS level bar SHALL display a ▲ character at the horizontal position corresponding to the currently selected threshold, so the user can see where the VAD trigger point sits relative to their voice level.

#### Scenario: Marker position reflects threshold
- **WHEN** the threshold is set to value T and the maximum RMS display is R
- **THEN** the ▲ marker SHALL appear at column `floor(T / R * bar_width)` of the level bar

#### Scenario: Voice detection status label updates live
- **WHEN** the live RMS level equals or exceeds the current threshold
- **THEN** a status label SHALL read "● Voice detected" in green
- **WHEN** the live RMS level is below the threshold
- **THEN** the status label SHALL read "○ Silence" in a muted style

### Requirement: Threshold is adjusted with arrow keys
←/→ adjust the threshold by a coarse step; ↑/↓ adjust by a fine step. The threshold label updates immediately on every keypress.

#### Scenario: Right arrow increases threshold (coarse)
- **WHEN** the user presses →
- **THEN** the threshold SHALL increase by a coarse step (50 RMS), clamped to the maximum

#### Scenario: Left arrow decreases threshold (coarse)
- **WHEN** the user presses ←
- **THEN** the threshold SHALL decrease by a coarse step (50 RMS), minimum 1 RMS

#### Scenario: Up arrow increases threshold (fine)
- **WHEN** the user presses ↑
- **THEN** the threshold SHALL increase by a fine step (10 RMS), clamped to the maximum

#### Scenario: Down arrow decreases threshold (fine)
- **WHEN** the user presses ↓
- **THEN** the threshold SHALL decrease by a fine step (10 RMS), minimum 1 RMS

#### Scenario: Threshold label shows current value
- **WHEN** the threshold is adjusted
- **THEN** a label SHALL display the current threshold as an integer (e.g. "Threshold: 250")

### Requirement: Enter confirms and Escape cancels
Pressing Enter SHALL dismiss the screen with the chosen threshold float. Pressing Escape SHALL dismiss with None, leaving settings unchanged.

#### Scenario: Enter dismisses with threshold float
- **WHEN** the user presses Enter
- **THEN** the screen SHALL dismiss and the caller SHALL receive the current threshold as a float

#### Scenario: Escape dismisses with no change
- **WHEN** the user presses Escape
- **THEN** the screen SHALL dismiss and the caller SHALL receive None, leaving settings unchanged

#### Scenario: No visual glitch on dismiss
- **WHEN** the user presses Enter or Escape
- **THEN** the screen SHALL freeze its display immediately and not re-render during the dismiss animation
