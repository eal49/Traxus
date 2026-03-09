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
The client SHALL play received audio frames from the server using sounddevice. Each received binary frame is decoded using `shared/voice_protocol.unpack_s2c()` and the PCM bytes are played back non-blockingly.

#### Scenario: Received frame is played
- **WHEN** the client receives a binary frame while in the corresponding voice channel
- **THEN** the PCM data is passed to `sounddevice.play()` with `samplerate=16000`

---

### Requirement: Asyncio-safe callback bridging
The sounddevice callback thread SHALL communicate with the asyncio event loop via `loop.call_soon_threadsafe()`. The `AudioEngine.start()` method SHALL capture the running loop reference. The `AudioEngine.stop()` method SHALL clear the loop reference before the capture stream is closed.

#### Scenario: Callback enqueues safely
- **WHEN** a PCM block arrives in the sounddevice callback thread during PTT
- **THEN** it is posted to the asyncio queue via `call_soon_threadsafe` without raising a RuntimeError
