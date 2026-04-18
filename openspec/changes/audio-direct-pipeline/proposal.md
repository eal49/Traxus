## Why

Every received audio frame flows through Textual's message bus before reaching the playback queue, adding 0–50 ms of unpredictable latency per frame that defeats the jitter buffer. On the send side, frames cross two asyncio queues and three coroutine context switches before leaving the socket, adding another 0–40 ms of variable delay. A third issue is that the server relays audio to multiple receivers sequentially rather than concurrently. Together these cause audio that is choppy and unintelligible even on a local network.

## What Changes

- **Receive path bypass**: `WsWorker._recv_loop` calls `AudioEngine.play()` directly for binary frames instead of posting an `AudioFrame` message through Textual's bus. The `on_traxus_app_audio_frame` handler and `TraxusApp.AudioFrame` message class are removed.
- **Send path collapse**: The intermediate `AudioEngine._queue` (asyncio.Queue) and `capture_loop` coroutine are eliminated. The sounddevice capture callback packs and enqueues the frame directly onto `WsWorker._binary_send_queue` via `call_soon_threadsafe`, reducing the send path from three event-loop context switches to one.
- **Concurrent server relay**: `MessageRouter.relay_voice` replaces its sequential `for` loop with `asyncio.gather()` so all receivers are sent frames in parallel.

## Capabilities

### New Capabilities

- `audio-direct-pipeline`: Defines the requirement that audio frames are delivered to the playback engine without passing through any UI message bus, and that frames are sent with the minimum number of asyncio hops.

### Modified Capabilities

- `audio-engine`: `capture_loop` is removed; the capture callback now posts directly to the ws-worker send queue. The `AudioFrame` message class is no longer part of the audio engine contract.

## Impact

- `client/ws_worker.py`: `_recv_loop` gains a reference to `AudioEngine`; binary frames decoded and played inline.
- `client/app.py`: `AudioFrame` message class removed; `on_traxus_app_audio_frame` handler removed; `capture_loop` call replaced by direct binary-queue wiring.
- `client/audio_engine.py`: `capture_loop` method and `self._queue` asyncio.Queue removed; capture callback posts packed frames directly.
- `server/message_router.py`: `relay_voice` switched from sequential awaits to `asyncio.gather()`.
- `tests/`: tests that reference `AudioFrame`, `capture_loop`, or `on_traxus_app_audio_frame` updated.
