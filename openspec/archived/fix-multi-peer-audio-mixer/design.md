## Context

Traxus uses aiortc for WebRTC voice. Each remote participant gets a `RemoteAudioSink` asyncio task that calls `await loop.run_in_executor(None, stream.write, pcm)` on a single shared `sd.OutputStream`. With 2 participants this serialises fine; with 3+ the concurrent writes interleave raw PCM buffers in PortAudio, producing choppy round-robin playback instead of mixed audio.

Current playback path:

```
RemoteAudioSink[B] ─────┐
                         ├──▶  sd.OutputStream  (race)
RemoteAudioSink[C] ─────┘
```

Target path:

```
RemoteAudioSink[B] ──▶ Queue[B] ──┐
                                    ├──▶ AudioMixer.run()  ──▶  sd.OutputStream
RemoteAudioSink[C] ──▶ Queue[C] ──┘        (one write / 20 ms)
```

## Goals / Non-Goals

**Goals:**
- Eliminate concurrent writes; one `sd.OutputStream.write()` call per 20 ms frame period
- Properly sum PCM from N speakers (float32 accumulation + int16 clip)
- Preserve per-user volume gain (already in RemoteAudioSink before enqueue)
- Keep output device hot-swap working
- No change to signalling, MicTrack, or the server

**Non-Goals:**
- Automatic gain control or noise suppression
- Echo cancellation
- Mixing more than a few dozen simultaneous speakers (no scalability concern at this scope)

## Decisions

### D1 — Timer-driven mixer, not frame-rendezvous

The mixer wakes on a 20 ms asyncio sleep, not by waiting for all N queues to have a frame.

**Why:** A rendezvous approach would stall playback if any one sink is slow (e.g. ICE restart, packet loss). A timer-driven approach fills missing slots with silence, matching how real audio mixers work and keeping latency constant regardless of per-peer jitter.

**Alternative considered:** `asyncio.gather` on all queues — rejected because it blocks the write on the slowest peer.

### D2 — AudioMixer owns the OutputStream and the mixer task

`PeerManager` constructs `AudioMixer` on voice join and calls `await mixer.close()` on leave. `AudioMixer` starts its own asyncio task internally via `asyncio.ensure_future`.

**Why:** Centralises all OutputStream lifecycle (open, write, hot-swap, close) in one class. `PeerManager` just manages slots: `add_user(username)` / `remove_user(username)`.

**Alternative considered:** mixer as a free coroutine passed to `run_worker` — rejected because slot lifecycle and stream swap would leak into PeerManager.

### D3 — RemoteAudioSink pushes to AudioMixer, not to a queue directly

`RemoteAudioSink` receives an `AudioMixer` reference and calls `mixer.push(username, pcm)`, which does a non-blocking `queue.put_nowait()` (drops frame on overflow, matching existing MicTrack behaviour).

**Why:** Keeps the push API simple; the mixer owns queue creation and sizing.

### D4 — Frame size normalisation in the mixer

The mixer reads at most one frame per slot per tick. If a slot has multiple queued frames (jitter burst), only one is consumed per tick to stay at real-time rate; excess frames are aged out if the queue exceeds `_QUEUE_MAX`.

**Why:** Prevents latency accumulation if a sink delivers frames faster than real-time for a moment.

### D5 — Output device hot-swap moves to AudioMixer

`AudioMixer.restart_output_stream(device)` replaces the existing `PeerManager.restart_output_stream`. Same open-swap-wait-close approach as the current implementation.

**Why:** AudioMixer is now the sole OutputStream owner; only it can safely swap it.

## Risks / Trade-offs

- **20 ms mixer tick drift** — `asyncio.sleep(0.020)` is approximate; cumulative drift could cause occasional double or skipped writes. Mitigation: use absolute target timestamps (same pattern as `MicTrack.recv()`).
- **Executor thread pressure** — the single `run_in_executor` write is unchanged; no new thread pressure introduced.
- **Test isolation** — `AudioMixer` starts an internal asyncio task; tests must cancel it explicitly or use `IsolatedAsyncioTestCase` with proper teardown.

## Migration Plan

1. Add `client/audio_mixer.py` (new file, no risk).
2. Update `RemoteAudioSink` to accept `AudioMixer` instead of `out_stream_holder`.
3. Update `PeerManager` to construct `AudioMixer`, pass it to sinks, and call `add_user`/`remove_user`.
4. Update `app.py` to no longer pass `out_stream` to `PeerManager` directly (AudioMixer owns it now — PeerManager still opens the stream and hands it to AudioMixer at construction).
5. Remove `PeerManager.restart_output_stream`; delegate to `AudioMixer`.
6. Run full test suite; fix any wiring breakage in existing tests.
7. Add `tests/test_audio_mixer.py`.

Rollback: revert `audio_mixer.py` and restore prior `remote_audio_sink.py` / `peer_manager.py` — no schema or protocol changes, so rollback is a pure file revert.

## Open Questions

- None blocking implementation.
