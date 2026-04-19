## Requirements

### Requirement: Graceful degradation when audio unavailable
If `import aiortc` or `import sounddevice` fails at runtime, the client SHALL start normally with all text features intact. Voice slash commands SHALL display a local error message instead of attempting audio I/O. PTT keybinding SHALL be silently ignored.

#### Scenario: Missing aiortc shows error on voice command
- **WHEN** aiortc is not installed and the user runs `/vjoin lounge`
- **THEN** a local error message `"Voice unavailable: aiortc not installed"` is displayed in the message view
- **THEN** no C2S message is sent to the server

#### Scenario: Missing sounddevice shows error on voice command
- **WHEN** sounddevice is not installed and the user runs `/vjoin lounge`
- **THEN** a local error message `"Voice unavailable: sounddevice not installed"` is displayed in the message view
- **THEN** no C2S message is sent to the server

---

### Requirement: AudioEngine supports VAD callback
The AudioEngine SHALL accept a VAD callback that is fired (via call_soon_threadsafe) on voice/silence state transitions when VAD mode is active.

#### Scenario: Callback fires on voice onset
- **WHEN** a VAD callback is registered and microphone energy crosses the threshold from below to above
- **THEN** the callback SHALL be invoked with `True` on the asyncio event loop

#### Scenario: Callback fires on silence onset
- **WHEN** a VAD callback is registered and microphone energy crosses the threshold from above to below
- **THEN** the callback SHALL be invoked with `False` on the asyncio event loop

#### Scenario: Callback not invoked when state unchanged
- **WHEN** a VAD callback is registered and microphone energy stays above (or stays below) the threshold
- **THEN** the callback SHALL NOT be invoked

---

### Requirement: AudioEngine start() is idempotent
Calling `AudioEngine.start()` when the stream is already open SHALL be a no-op.

#### Scenario: Double start does not crash
- **WHEN** `AudioEngine.start()` is called while the stream is already open
- **THEN** no exception is raised and the existing stream remains open

---

### Requirement: AudioEngine supports a spectrum callback
`AudioEngine` SHALL expose a `set_spectrum_callback(cb)` method. When set, `cb`
SHALL be called on the asyncio event loop (via `call_soon_threadsafe`) once per
captured frame, receiving the NS-filtered (or raw) PCM as `bytes`. The callback
SHALL only be invoked when the mic stream is open. Setting the callback to `None`
SHALL disable it.

#### Scenario: Spectrum callback receives PCM bytes each frame
- **WHEN** `set_spectrum_callback(cb)` has been called and the mic stream is open
- **THEN** `cb` SHALL be invoked on every captured frame with the PCM bytes as its sole argument

#### Scenario: Spectrum callback receives NS-filtered bytes when NS is on
- **WHEN** `noise_suppression_enabled` is `True` and the spectrum callback is set
- **THEN** the bytes passed to the callback SHALL be the NS-filtered PCM

#### Scenario: No spectrum callback invocation when not set
- **WHEN** `set_spectrum_callback(None)` has been called
- **THEN** the audio thread SHALL NOT attempt to invoke a spectrum callback
