### Requirement: Graceful degradation when sounddevice unavailable
If `import sounddevice` fails at runtime, the client SHALL start normally with all text features intact. Voice slash commands SHALL display a local error message instead of attempting audio I/O. PTT keybinding SHALL be silently ignored.

#### Scenario: Missing sounddevice shows error on voice command
- **WHEN** sounddevice is not installed and the user runs `/vjoin lounge`
- **THEN** a local error message `"Voice unavailable: sounddevice not installed"` is displayed in the message view
- **THEN** no C2S message is sent to the server

---

### Requirement: Push-to-talk toggle
The client SHALL support a Ctrl+M keybinding that toggles microphone transmission on and off. The status bar SHALL show `[● MIC]` in red while transmitting and nothing (or a neutral indicator) when idle.

#### Scenario: Ctrl+M starts transmission
- **WHEN** the user presses Ctrl+M and is in a voice channel and sounddevice is available
- **THEN** mic capture starts and binary audio frames are sent to the server

#### Scenario: Ctrl+M stops transmission
- **WHEN** the user presses Ctrl+M while already transmitting
- **THEN** mic capture stops and no further audio frames are sent

#### Scenario: PTT outside voice channel shows hint
- **WHEN** the user presses Ctrl+M but is not in any voice channel
- **THEN** a local hint message is displayed (`"Join a voice channel first with /vjoin <channel>"`)
- **THEN** no audio capture starts

---

### Requirement: Audio capture parameters
The audio engine SHALL capture microphone input at 16 000 Hz, mono (1 channel), 16-bit signed integer (int16), with a block size of 320 samples (20 ms frames).

#### Scenario: Capture uses correct parameters
- **WHEN** PTT is activated
- **THEN** the sounddevice InputStream is opened with `samplerate=16000`, `channels=1`, `dtype='int16'`, `blocksize=320`

---

### Requirement: Audio playback
The client SHALL play received audio frames from the server using sounddevice. Each received binary frame is decoded using `shared/voice_protocol.unpack_s2c()`, the codec tag is read, the audio payload is decoded if necessary (ADPCM → PCM), and the resulting PCM bytes are played back non-blockingly.

#### Scenario: Received ADPCM frame is decoded and played
- **WHEN** the client receives a binary frame with codec tag `0x01` (ADPCM) while in the corresponding voice channel
- **THEN** the audio payload SHALL be decoded to PCM via `shared/adpcm.decode()` before being passed to playback

#### Scenario: Received raw PCM frame is played directly
- **WHEN** the client receives a binary frame with codec tag `0x00` (raw PCM)
- **THEN** the audio payload SHALL be passed to playback without transformation

---

### Requirement: Asyncio-safe callback bridging
The sounddevice callback thread SHALL communicate with the asyncio event loop via `loop.call_soon_threadsafe()`. The `AudioEngine.start()` method SHALL capture the running loop reference. The `AudioEngine.stop()` method SHALL clear the loop reference before the capture stream is closed.

#### Scenario: Callback enqueues safely
- **WHEN** a PCM block arrives in the sounddevice callback thread during PTT
- **THEN** it is posted to the asyncio queue via `call_soon_threadsafe` without raising a RuntimeError

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

### Requirement: AudioEngine encodes captured audio to ADPCM
When ADPCM is available (numpy importable), the AudioEngine SHALL encode captured PCM frames to ADPCM before queuing them for transmission. If noise suppression is also available (`NS_AVAILABLE` is `True`), the NS filter SHALL be applied to the PCM frame before ADPCM encoding.

The processing order for a captured frame is:
1. (Optional) `_SpectralNoiseSuppressor.process(pcm)` — only when `NS_AVAILABLE` is `True`
2. `shared/adpcm.encode(pcm)` — only when ADPCM is available
3. Place encoded (or raw) frame on the capture queue

#### Scenario: Captured frame is noise-suppressed then compressed before queuing
- **WHEN** PTT is active and a PCM block arrives in the sounddevice callback and both `NS_AVAILABLE` and ADPCM are available
- **THEN** the block SHALL first be passed through `_SpectralNoiseSuppressor.process()`, then encoded via `shared/adpcm.encode()` before being placed on the capture queue

#### Scenario: Captured frame is compressed before queuing (NS unavailable)
- **WHEN** PTT is active and a PCM block arrives in the sounddevice callback and ADPCM is available but `NS_AVAILABLE` is `False`
- **THEN** the block SHALL be encoded via `shared/adpcm.encode()` before being placed on the capture queue (no NS filter applied)

#### Scenario: Fallback to raw PCM when numpy unavailable
- **WHEN** numpy is not importable at startup
- **THEN** the AudioEngine SHALL queue raw PCM bytes and set codec tag to `0x00`
