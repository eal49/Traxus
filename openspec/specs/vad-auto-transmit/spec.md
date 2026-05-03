### Requirement: PTT key is a no-op in VAD mode
When PTT mode is `"vad"`, pressing the PTT key or activating the `ptt_toggle` action SHALL have no effect on transmission state. VAD auto-transmit is the exclusive gate for starting and stopping audio in this mode.

#### Scenario: PTT key press is ignored in VAD mode
- **WHEN** PTT mode is `"vad"` and the user presses the configured PTT key
- **THEN** `toggle_ptt()` SHALL NOT be called and transmission state SHALL remain unchanged

#### Scenario: ptt_toggle action is a no-op in VAD mode
- **WHEN** PTT mode is `"vad"` and the `action_ptt_toggle` action fires (e.g., via F9 binding)
- **THEN** `toggle_ptt()` SHALL NOT be called and transmission state SHALL remain unchanged

#### Scenario: Mouse PTT button is ignored in VAD mode
- **WHEN** PTT mode is `"vad"` and the user clicks the configured mouse PTT button
- **THEN** `toggle_ptt()` SHALL NOT be called and transmission state SHALL remain unchanged

### Requirement: VAD mode activates transmission on voice detection
When PTT mode is set to VAD, the client SHALL automatically start transmitting when microphone energy exceeds the configured threshold, and stop transmitting after 400ms of silence.

#### Scenario: Voice onset starts transmission
- **WHEN** PTT mode is `"vad"` and the user is in a voice channel and microphone energy exceeds the threshold
- **THEN** the client SHALL start transmitting immediately (equivalent to `start_ptt()`)

#### Scenario: Silence after hangover stops transmission
- **WHEN** PTT mode is `"vad"` and the user is transmitting and microphone energy has been below the threshold for 400ms
- **THEN** the client SHALL stop transmitting (equivalent to `stop_ptt()`)

#### Scenario: Brief silence within hangover does not stop transmission
- **WHEN** PTT mode is `"vad"` and the user is transmitting and microphone energy drops below threshold but voice resumes within 400ms
- **THEN** the client SHALL remain transmitting without interruption

#### Scenario: VAD requires voice channel
- **WHEN** PTT mode is `"vad"` and the user is not in a voice channel
- **THEN** VAD monitoring SHALL not start transmission and SHALL display a hint to join a voice channel

### Requirement: VAD mic stream stays open while in voice channel
In VAD mode, the microphone input stream SHALL remain open continuously while the user is in a voice channel, regardless of whether transmission is active. If the stream is closed by an internal operation (e.g., VAD calibration), the client SHALL restart it asynchronously without blocking the UI.

#### Scenario: Mic opens on voice channel join in VAD mode
- **WHEN** PTT mode is `"vad"` and the user joins a voice channel
- **THEN** the microphone input stream SHALL open and VAD monitoring SHALL begin

#### Scenario: Mic closes on voice channel leave in VAD mode
- **WHEN** PTT mode is `"vad"` and the user leaves the voice channel
- **THEN** the microphone input stream SHALL close and VAD monitoring SHALL stop

#### Scenario: Mic stream not opened by PTT key in VAD mode
- **WHEN** PTT mode is `"vad"` and the user presses the PTT key
- **THEN** no additional stream SHALL be opened (stream already open from vjoin)

#### Scenario: VAD stream restarts after calibration screen closes
- **WHEN** PTT mode is `"vad"` and the user is in a voice channel and the VAD calibration screen closes
- **THEN** the client SHALL restart the VAD mic stream asynchronously, with a short delay to allow the audio driver to release the device, and VAD monitoring SHALL resume with the new threshold

### Requirement: VAD sensitivity is user-configurable
The VAD RMS energy threshold SHALL be adjustable via four named levels or a custom numeric value, all persisted to settings.

#### Scenario: Low sensitivity requires loud speech
- **WHEN** VAD sensitivity is `"low"`
- **THEN** only high-energy audio (RMS ≥ 200 on int16 scale) SHALL trigger transmission

#### Scenario: Medium sensitivity is balanced
- **WHEN** VAD sensitivity is `"medium"`
- **THEN** moderate-energy audio (RMS ≥ 100) SHALL trigger transmission

#### Scenario: High sensitivity (default) detects quiet speech
- **WHEN** VAD sensitivity is `"high"`
- **THEN** low-energy audio (RMS ≥ 50) SHALL trigger transmission

#### Scenario: Very high sensitivity detects whispers
- **WHEN** VAD sensitivity is `"very_high"`
- **THEN** very low-energy audio (RMS ≥ 20) SHALL trigger transmission

#### Scenario: Custom sensitivity uses saved numeric threshold
- **WHEN** VAD sensitivity is `"custom"`
- **THEN** the RMS threshold SHALL be read from `vad_custom_threshold` in settings (default 50.0)

#### Scenario: Default sensitivity is high
- **WHEN** no `vad_sensitivity` key exists in settings
- **THEN** the client SHALL behave as if sensitivity is `"high"`

#### Scenario: Default custom threshold is 50.0
- **WHEN** `vad_sensitivity` is `"custom"` and no `vad_custom_threshold` key exists in settings
- **THEN** the client SHALL use a threshold of 50.0
