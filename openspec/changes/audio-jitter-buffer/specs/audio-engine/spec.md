## MODIFIED Requirements

### Requirement: Audio playback
The client SHALL play received audio frames from the server using sounddevice. Each received binary frame is decoded using `shared/voice_protocol.unpack_s2c()`, the codec tag is read, the audio payload is decoded if necessary (ADPCM → PCM), and the resulting PCM bytes are queued for playback via the jitter buffer. The output stream SHALL be opened with `latency="low"`. Frames SHALL be played at a fixed 20 ms clock after the jitter buffer is primed.

#### Scenario: Received ADPCM frame is decoded and played
- **WHEN** the client receives a binary frame with codec tag `0x01` (ADPCM) while in the corresponding voice channel
- **THEN** the audio payload SHALL be decoded to PCM via `shared/adpcm.decode()` before being passed to playback

#### Scenario: Received raw PCM frame is played directly
- **WHEN** the client receives a binary frame with codec tag `0x00` (raw PCM)
- **THEN** the audio payload SHALL be passed to playback without transformation

#### Scenario: Playback uses low-latency output stream
- **WHEN** `_playback_worker` opens `sd.OutputStream`
- **THEN** the stream SHALL be initialized with `latency="low"`
