## Context

`AudioEngine._playback_worker` currently calls `queue.get()` and immediately writes each frame to `sd.OutputStream`. Frames produced by the sender every 20 ms arrive at the receiver with variable inter-packet delay due to TCP scheduling and OS networking stack variance. This timing variance is replicated verbatim in playback, producing audible stutter. Additionally, when `_play_queue` fills, the current code drops the oldest buffered frame — mid-stream — creating waveform discontinuities heard as clicks.

The fix is a fixed-delay jitter buffer: accumulate a small number of frames before starting playback, then drain at a steady 20 ms clock. Network bursts fill the buffer; gaps are absorbed by the pre-filled depth. Drop-newest replaces drop-oldest so already-buffered audio is never interrupted.

## Goals / Non-Goals

**Goals:**
- Eliminate stutter caused by variable frame arrival timing.
- Eliminate clicks caused by drop-oldest queue overflow.
- Keep `play()` non-blocking (nanosecond return, no lock contention).
- Configurable buffer depth (default 60 ms = 3 frames).
- No protocol or server changes.

**Non-Goals:**
- Opus codec replacement (separate future change).
- Adaptive jitter buffer (buffer depth stays fixed for now).
- Concealment of lost frames (silence is acceptable for now).
- UI exposure of the jitter buffer setting (settings.json only).

## Decisions

### D1: Fixed-delay buffer implemented as a pre-fill gate in `_playback_worker`

The playback thread blocks on `queue.get()` until the queue depth reaches `jitter_buffer_frames`, then switches to a timed drain: `queue.get(timeout=FRAME_SECONDS)` on a 20 ms interval. If the queue empties (underrun), the thread waits silently and re-enters the pre-fill gate on the next frame.

**Alternative considered:** A separate `collections.deque` accumulator with a threading.Event trigger. Rejected because the existing `queue.Queue` already provides the needed blocking semantics without a second synchronisation primitive.

**Alternative considered:** `threading.Timer` to enforce the 20 ms clock. Rejected because `Timer` drift accumulates; `time.perf_counter` with a busy-sleep corrects for loop overhead each iteration.

### D2: Drop-newest on overflow in `play()`

When `_play_queue` is full, the new frame is discarded rather than the oldest. This preserves continuity in already-buffered audio.

**Alternative considered:** Keep drop-oldest but increase `_PLAY_QUEUE_MAX`. Rejected — a larger queue just delays the click, doesn't remove it.

### D3: `latency="low"` on `sd.OutputStream`

Passes `latency="low"` to sounddevice, which selects the minimum stable latency the OS audio subsystem supports (typically 5–20 ms on Windows WASAPI, ~10 ms on Linux ALSA). This prevents the OS from adding its own unpredictable buffering on top of our jitter buffer.

**Alternative considered:** Explicit `latency=0.02` (20 ms). Rejected because the numeric value must match the hardware; `"low"` lets sounddevice pick the right value per platform.

### D4: `jitter_buffer_frames` stored in `settings.json` via `_DEFAULTS`

Default value 3 (60 ms). Adding it to `_DEFAULTS` in `client/settings.py` means it is automatically populated for existing users on first load. `AudioEngine` reads it from the settings dict passed to its constructor or via a setter.

**Alternative considered:** Hardcode the constant in `audio_engine.py`. Rejected — users on high-latency connections need to increase it; a setting is more flexible.

## Risks / Trade-offs

- **Added latency**: The jitter buffer introduces a fixed 60 ms delay (at default depth 3). This is imperceptible in PTT walkie-talkie usage but would be noticeable in a duplex conversation. Acceptable for current PTT-only use.
  → Mitigation: configurable via `jitter_buffer_frames`; users on LAN can set it to 1.

- **Underrun silence**: If the network drops 3+ consecutive frames, the buffer empties and the playback thread produces silence until the next frame refills the gate. No concealment.
  → Mitigation: out of scope for this change; acceptable degradation.

- **Clock drift**: The 20 ms drain clock is based on `time.perf_counter`. Small drift (~0.1 ms/frame) accumulates but is inaudible at 20 ms frame size.
  → Mitigation: recalibrate `next_tick` on each iteration to absorb loop overhead.

## Migration Plan

1. Existing users get `jitter_buffer_frames: 3` auto-added to `settings.json` on first launch (handled by `settings.py` `_DEFAULTS` merge).
2. No server restart required. No protocol change.
3. Rollback: revert `audio_engine.py` and `settings.py`; audio reverts to direct playback.

## Open Questions

- Should the jitter buffer depth auto-increase if underruns are detected? Punted to a follow-up adaptive buffer change.
- Should we expose `jitter_buffer_frames` in `SettingsScreen`? Punted — settings.json edit is sufficient for now.
