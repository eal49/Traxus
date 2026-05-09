## Requirements

### Requirement: AudioMixer owns the OutputStream and is the sole writer
The system SHALL implement an `AudioMixer` class in `client/audio_mixer.py` that is the exclusive writer to the `sd.OutputStream`. No other component SHALL call `stream.write()` directly for remote audio playback. `AudioMixer` SHALL start an internal asyncio task (`run()`) that writes one mixed PCM frame to the OutputStream every 20 ms.

#### Scenario: Only one write per frame period regardless of speaker count
- **WHEN** two or more remote participants are simultaneously producing audio frames
- **THEN** the AudioMixer SHALL produce exactly one `stream.write()` call per 20 ms tick containing the sum of all available frames

#### Scenario: Mixer task starts on construction
- **WHEN** `AudioMixer` is instantiated
- **THEN** it SHALL schedule its internal `run()` coroutine as an asyncio task automatically

---

### Requirement: AudioMixer mixes PCM by float32 summation with int16 clipping
The AudioMixer SHALL sum PCM frames from all active user slots as `float32` arrays and clip the result to the int16 range `[-32768, 32767]` before writing. This prevents integer overflow when multiple speakers are simultaneously active.

#### Scenario: Two speakers summed correctly
- **WHEN** two users each have a queued frame of non-zero int16 PCM
- **THEN** the mixer SHALL produce a frame equal to `np.clip(frame_A + frame_B, -32768, 32767).astype(np.int16)`

#### Scenario: Single speaker passes through unchanged
- **WHEN** exactly one user has a queued frame and all others are silent
- **THEN** the mixer output SHALL equal that user's frame (no distortion from single-speaker mixing)

#### Scenario: No speakers produces silence
- **WHEN** no user has a queued frame
- **THEN** the mixer SHALL write a zeroed int16 frame of the standard frame size

---

### Requirement: AudioMixer fills missing frames with silence
If a user slot has no queued frame when the mixer tick fires, the AudioMixer SHALL contribute silence (zeros) for that slot rather than stalling the mixer tick.

#### Scenario: Slow sink does not stall mixer
- **WHEN** a remote sink has not yet pushed a frame for the current tick
- **THEN** the mixer SHALL proceed with zeros for that slot and write on schedule

#### Scenario: Late frame is consumed on the next tick
- **WHEN** a sink pushes two frames in rapid succession after a missed tick
- **THEN** the mixer SHALL consume one frame per tick to maintain real-time pacing, dropping excess frames if the queue exceeds the maximum depth

---

### Requirement: AudioMixer supports dynamic user slot management
The AudioMixer SHALL expose `add_user(username: str)` and `remove_user(username: str)` methods. `add_user` creates a per-user `asyncio.Queue` slot; `remove_user` drains and discards it.

#### Scenario: User slot added mid-session
- **WHEN** a new participant joins an active voice channel
- **THEN** `add_user` SHALL create a queue slot that the mixer includes in subsequent ticks

#### Scenario: User slot removed on disconnect
- **WHEN** a participant leaves the voice channel
- **THEN** `remove_user` SHALL discard that user's queue slot
- **THEN** subsequent mixer ticks SHALL NOT include that user's audio

---

### Requirement: AudioMixer supports output device hot-swap
The AudioMixer SHALL expose `restart_output_stream(device: str | None)` that replaces the internal `sd.OutputStream` atomically: open new stream, swap reference, wait one frame budget, close old stream.

#### Scenario: Device swap does not interrupt playback for connected peers
- **WHEN** `restart_output_stream` is called while peers are active
- **THEN** playback SHALL resume on the new device within one frame period
- **THEN** no exception SHALL propagate to the caller

---

### Requirement: AudioMixer closes cleanly
`AudioMixer.close()` SHALL cancel the internal mixer task, stop and close the OutputStream, and drain all user queues.

#### Scenario: Close is safe to call when no users are connected
- **WHEN** `AudioMixer.close()` is called with an empty user slot map
- **THEN** it SHALL complete without raising an exception

#### Scenario: Close stops the mixer task
- **WHEN** `AudioMixer.close()` is awaited
- **THEN** the internal `run()` task SHALL be cancelled and awaited to completion
