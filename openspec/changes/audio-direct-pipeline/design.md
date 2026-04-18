## Context

The current audio pipeline has three sources of variable latency that combine to make audio choppy even on a LAN:

**Receive path (0–50 ms per frame):** `WsWorker._recv_loop` calls `app.post_message(AudioFrame(raw))`. Textual enqueues the message internally and dispatches it when its message pump next runs. The pump is on the same asyncio event loop as rendering and all other Textual message handling. When the UI is active, this delays every audio frame by an unpredictable 0–50 ms.

**Send path (0–40 ms per frame):** The sounddevice callback posts to `AudioEngine._queue` (asyncio.Queue #1) via `call_soon_threadsafe`. `capture_loop` awaits that queue, then calls `enqueue_binary` which posts to `WsWorker._binary_send_queue` (asyncio.Queue #2). `_send_loop` then awaits that queue and calls `ws.send()`. Three coroutine context switches, two queues — each one a potential stall when the event loop is busy.

**Server relay (sequential, 0–5 ms × N receivers):** `relay_voice` iterates receivers and `await`s each `ws.send()` in turn. With N listeners, frame N is delayed by the time to send frames 1…N-1.

## Goals / Non-Goals

**Goals:**
- Remove Textual message bus from the receive audio path entirely.
- Reduce send-side asyncio hops from 3 to 1.
- Make server relay concurrent across all receivers.
- Keep `play()` non-blocking (still just a `queue.put_nowait`).
- Maintain thread safety — sounddevice callback is not on the asyncio loop.

**Non-Goals:**
- Codec change (ADPCM → Opus). Separate future change.
- UDP transport. Separate future change.
- Exposing pipeline metrics to the UI.

## Decisions

### D1: WsWorker holds a direct reference to AudioEngine

`WsWorker` is constructed in `TraxusApp.connect_to_server`. At that point `self._audio_engine` already exists. Passing it into `WsWorker.__init__` gives `_recv_loop` a direct reference with no coupling to Textual internals.

**Alternative considered:** Keep `post_message` but make `AudioFrame` bypass the Textual bus via a low-level asyncio callback. Rejected — Textual does not expose a public API for this; it would require monkey-patching internals.

**Alternative considered:** Thread-safe callback registered on the engine, called from `_recv_loop`. Equivalent complexity to a direct reference, no benefit.

### D2: `_recv_loop` calls `unpack_s2c` + `engine.play()` inline

`unpack_s2c` is pure Python doing a handful of slice operations — under 1 µs. `play()` is `queue.put_nowait()` — nanoseconds. Both are safe to call from an asyncio coroutine on the event loop without blocking it. No thread handoff needed.

**Alternative considered:** Offload `unpack_s2c` to a threadpool executor. Rejected — unnecessary overhead for a sub-microsecond operation.

### D3: Capture callback posts packed frame directly to `_binary_send_queue`

The sounddevice callback runs on a dedicated audio thread. It cannot `await`. It currently uses `loop.call_soon_threadsafe(self._queue.put_nowait, ...)` to hand off to the asyncio event loop. 

The new approach: encode + pack the frame in the audio thread itself (ADPCM encode is ~0.1 ms, pack_c2s is ~0.01 ms — both acceptable in a 20 ms callback budget), then call `loop.call_soon_threadsafe(_binary_send_queue.put_nowait, packed_frame)` directly. This eliminates the intermediate `_queue` and the `capture_loop` coroutine entirely.

`_binary_send_queue` is `asyncio.Queue` — `put_nowait` is safe to call from `call_soon_threadsafe`.

**Alternative considered:** Keep `capture_loop` but make it call `ws.send()` directly instead of `enqueue_binary`. Rejected — `capture_loop` lives in `AudioEngine`; giving it a WebSocket reference couples audio engine to transport, bad separation of concerns.

**Impact on `capture_loop`:** The method is removed. PTT start/stop logic in `app.py` that currently starts `capture_loop` as a worker is replaced by wiring the send reference into the engine before activating PTT.

### D4: `send_fn` replaced by passing `(loop, binary_send_queue, channel)` into engine

`AudioEngine` needs three things to post a packed frame: the asyncio event loop reference (already stored as `self._loop`), the binary send queue, and the current voice channel name. The channel is already known at PTT start time. A new method `AudioEngine.set_send_target(binary_send_queue, channel)` is called when the user joins a voice channel and clears when they leave. The capture callback uses these internally.

**Alternative considered:** Pass a callable `send_fn` as before. A callable is cleaner but the previous `send_fn` was async (`await send_fn(...)`) requiring `capture_loop` as its runner. A sync `put_nowait` approach doesn't need a runner coroutine at all.

### D5: Server `relay_voice` uses `asyncio.gather` with `return_exceptions=True`

Wrapping all `vc.ws.send()` calls in `asyncio.gather(..., return_exceptions=True)` sends them concurrently. `return_exceptions=True` prevents a single failed send (disconnecting client) from cancelling the others.

**Alternative considered:** `asyncio.create_task` per receiver, fire-and-forget. Equivalent concurrency, but tasks that raise exceptions would be silently swallowed without `return_exceptions`. `gather` is cleaner.

## Risks / Trade-offs

- **ADPCM encode in audio thread**: Moves ~0.1 ms of CPU work into the sounddevice callback. The callback budget at 50 fps is 20 ms — 0.1 ms is 0.5% of the budget. Acceptable.
  → Mitigation: if profiling shows an issue, offload encode to a thread; but this is unlikely.

- **WsWorker coupled to AudioEngine**: `WsWorker` now holds an `AudioEngine` reference. These were previously decoupled via Textual messages.
  → Mitigation: the coupling is one-directional and contained to `__init__` and `_recv_loop`. AudioEngine has no reference back to WsWorker.

- **Removing `AudioFrame` message class breaks any external code relying on it**: Only internal — tests will need updating.
  → Mitigation: covered in task list.

- **`set_send_target` must be cleared on voice leave**: If the engine retains a stale queue reference after disconnect, it will silently drop frames.
  → Mitigation: `set_send_target(None, "")` called on voice leave and on disconnect.

## Migration Plan

1. No server config changes. Server change (D5) is backward compatible — receivers get frames in the same format.
2. Client changes are internal; no protocol change.
3. Rollback: revert the four changed files; audio returns to Textual-pump path.

## Open Questions

- Should `AudioEngine.set_send_target` be renamed to better reflect its role? `set_voice_send(queue, channel)` might be clearer. Punted — can rename in implementation.
