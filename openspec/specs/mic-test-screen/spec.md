## Requirements

### Requirement: MicTestScreen displays a live spectrogram
`MicTestScreen` SHALL render a rolling ASCII spectrogram (frequency × time) built
from `numpy.fft.rfft` on each incoming PCM frame. The display SHALL be 48 columns
wide and 16 rows tall, with the lowest frequency at the bottom and the highest at
the top. Each column represents one FFT frame; the display scrolls left as new
frames arrive. Intensity SHALL be encoded using the four Unicode block characters
`░▒▓█` plus space for silence, mapped to five magnitude thresholds.

#### Scenario: Spectrogram updates on each audio frame
- **WHEN** a PCM frame arrives from the microphone
- **THEN** a new column SHALL be appended to the right of the spectrogram and the oldest column dropped from the left

#### Scenario: Silence renders as empty columns
- **WHEN** the microphone captures silence (all samples near zero)
- **THEN** the new spectrogram column SHALL consist entirely of space characters

#### Scenario: Loud broadband signal fills the spectrogram
- **WHEN** the microphone captures broadband noise at high amplitude
- **THEN** the new column SHALL contain `▓` or `█` characters across multiple frequency rows

---

### Requirement: MicTestScreen displays a live RMS level bar
`MicTestScreen` SHALL render a horizontal RMS level bar (0–100%) updated on each
audio frame, showing the current input loudness.

#### Scenario: Level bar reflects input loudness
- **WHEN** the user speaks into the microphone
- **THEN** the level bar width SHALL increase proportionally to the RMS energy of the captured signal

#### Scenario: Silence shows empty level bar
- **WHEN** no sound is captured
- **THEN** the level bar SHALL be empty (0%)

---

### Requirement: MicTestScreen provides audio loopback
`MicTestScreen` SHALL route captured (and NS-filtered, if NS is enabled) PCM audio
directly to the playback queue so the user hears themselves through their speakers.
Loopback SHALL be enabled by default when the screen opens.

#### Scenario: Loopback on by default
- **WHEN** `MicTestScreen` opens
- **THEN** `AudioEngine.loopback_enabled` SHALL be `True`

#### Scenario: Loopback plays NS-filtered audio
- **WHEN** `noise_suppression_enabled` is `True` and loopback is active
- **THEN** the audio played back SHALL be the NS-filtered PCM, not the raw PCM

#### Scenario: Loopback plays raw audio when NS is off
- **WHEN** `noise_suppression_enabled` is `False` and loopback is active
- **THEN** the audio played back SHALL be the raw captured PCM

#### Scenario: Loopback toggle with L key
- **WHEN** the user presses `L` while `MicTestScreen` is open
- **THEN** `AudioEngine.loopback_enabled` SHALL toggle between `True` and `False`
- **THEN** the screen SHALL display the current loopback state ("Loopback: On" / "Loopback: Off")

---

### Requirement: MicTestScreen stops loopback and mic on close
When `MicTestScreen` is dismissed, it SHALL set `AudioEngine.loopback_enabled` to
`False` and stop the microphone stream.

#### Scenario: Unmount disables loopback
- **WHEN** the user presses Escape to close `MicTestScreen`
- **THEN** `AudioEngine.loopback_enabled` SHALL be `False` after the screen closes

#### Scenario: Unmount stops mic stream
- **WHEN** `MicTestScreen` closes
- **THEN** `AudioEngine.stop_vad()` SHALL have been called

---

### Requirement: MicTestScreen shows NS status
`MicTestScreen` SHALL display a static label indicating whether noise suppression
is currently enabled, so the user knows what they are hearing in the loopback.

#### Scenario: NS on label displayed
- **WHEN** `AudioEngine.noise_suppression_enabled` is `True`
- **THEN** the screen SHALL display "Noise Suppression: On"

#### Scenario: NS off label displayed
- **WHEN** `AudioEngine.noise_suppression_enabled` is `False`
- **THEN** the screen SHALL display "Noise Suppression: Off"
