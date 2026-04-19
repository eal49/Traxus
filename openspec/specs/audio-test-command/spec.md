## ADDED Requirements

### Requirement: /audioTest command sends synthetic tones over active voice channel
The client SHALL provide an `/audioTest` slash command that generates 10 sine-wave tones and injects them as binary audio frames into the WebSocket send pipeline, relaying them through the server to all other clients in the same voice channel.

#### Scenario: Command rejected when not in a voice channel
- **WHEN** the user types `/audioTest` and `current_voice_channel` is empty
- **THEN** the client SHALL display a local message: "Join a voice channel first (/vjoin <channel>)."
- **THEN** no frames SHALL be injected

#### Scenario: Command rejected when not connected
- **WHEN** the user types `/audioTest` and `_ws_worker` is None
- **THEN** the client SHALL display a local message: "Not connected."
- **THEN** no frames SHALL be injected

#### Scenario: Command rejected when audio unavailable
- **WHEN** the user types `/audioTest` and `AUDIO_AVAILABLE` is False
- **THEN** the client SHALL display a local message: "Voice not available: sounddevice/numpy not installed."
- **THEN** no frames SHALL be injected

#### Scenario: Command plays 10 tones in sequence
- **WHEN** the command is accepted and all guards pass
- **THEN** the client SHALL inject 50 binary frames per tone (500 frames total) into `_binary_send_queue`
- **THEN** each frame SHALL contain 320 int16 PCM samples packed as a C2S voice frame with `CODEC_RAW`
- **THEN** frames SHALL be injected at a rate of one frame per 20 ms

#### Scenario: Tones use a musical scale
- **WHEN** the 10 tones are generated
- **THEN** each tone SHALL use a distinct frequency from the C major scale (C4 through E5: 261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25, 587.33, 659.25 Hz)
- **THEN** each tone SHALL last exactly 1 second (50 frames × 20 ms)

#### Scenario: No audible click between consecutive tones
- **WHEN** consecutive tones are played
- **THEN** each tone SHALL have a 10 ms (160 sample) cosine taper applied at its start and end
- **THEN** amplitude SHALL smoothly ramp from 0 to peak at the start and peak to 0 at the end of each tone

#### Scenario: Test completes and notifies user
- **WHEN** all 500 frames have been injected
- **THEN** the client SHALL display a local message: "Audio test complete."
- **THEN** `_audio_test_running` SHALL be set to False

### Requirement: /audioTest command is non-reentrant
The client SHALL prevent concurrent executions of `/audioTest`.

#### Scenario: Second invocation while test is running
- **WHEN** the user types `/audioTest` while a test is already in progress
- **THEN** the client SHALL display a local message: "Audio test already in progress."
- **THEN** no additional frames SHALL be injected

#### Scenario: Flag cleared on error
- **WHEN** the `_audio_test_task` coroutine raises an unexpected exception
- **THEN** `_audio_test_running` SHALL be reset to False
- **THEN** the command MAY be re-invoked after the error
