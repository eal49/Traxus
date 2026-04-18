## Why

Received audio is jittery and hard to understand. TCP/WebSocket inter-packet delay causes frames to arrive in uneven bursts; without a jitter buffer the playback thread replays that timing variance directly as audible stutter. A secondary issue is the drop-oldest queue strategy, which produces clicks and pops when the buffer overflows.

## What Changes

- Introduce a jitter buffer in `AudioEngine`: playback drains at a fixed 20 ms clock rather than "as fast as frames arrive", absorbing network timing variance before it reaches the speaker.
- Replace the drop-oldest overflow strategy with drop-newest (discard the late-arriving frame, keep already-buffered audio continuous).
- Add an explicit `latency="low"` parameter to `sd.OutputStream` to prevent OS-default over-buffering on Windows.
- Expose `jitter_buffer_frames` (default 3 = 60 ms) as a configurable setting in `settings.json`.

## Capabilities

### New Capabilities

- `audio-jitter-buffer`: Fixed-delay playback buffer that decouples frame arrival from frame playback to smooth network jitter.

### Modified Capabilities

- `audio-engine`: Playback overflow behaviour changes (drop-newest instead of drop-oldest); stream latency now explicitly set.

## Impact

- `client/audio_engine.py`: playback worker rewritten; `play()` overflow logic changed; `_play_queue` grows by a configurable target depth before draining begins.
- `client/settings.py`: new key `jitter_buffer_frames` (int, default 3).
- No server changes. No protocol changes. No UI changes (unless we expose the setting in `SettingsScreen` later).
- Existing tests for `AudioEngine` may need adjustment for the new drain timing.
