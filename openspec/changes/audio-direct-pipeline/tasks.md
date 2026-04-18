## 1. AudioEngine — send path refactor

- [x] 1.1 Remove `self._queue: asyncio.Queue` from `AudioEngine.__init__`
- [x] 1.2 Add `self._send_queue` and `self._send_channel` attributes (both `None`/`""` by default) to `AudioEngine.__init__`
- [x] 1.3 Add `set_send_target(binary_send_queue, channel: str)` method to `AudioEngine` that stores the queue and channel (accepts `None` to clear)
- [x] 1.4 In `_input_callback`, replace the `self._queue.put_nowait` block with: encode frame (ADPCM or raw), call `voice_protocol.pack_c2s(channel, audio_bytes, codec)`, then `loop.call_soon_threadsafe(_send_queue.put_nowait, packed_frame)` — only when `_transmitting` and `_send_queue` is not None
- [x] 1.5 Remove the `capture_loop` method from `AudioEngine` entirely

## 2. WsWorker — receive path bypass

- [x] 2.1 Add `audio_engine: AudioEngine | None = None` parameter to `WsWorker.__init__` and store as `self._audio_engine`
- [x] 2.2 In `WsWorker._recv_loop`, replace the `self._post_audio_frame(raw)` call with inline `unpack_s2c` + `self._audio_engine.play()`, wrapped in a try/except to silently drop malformed frames
- [x] 2.3 Remove the `_post_audio_frame` helper method from `WsWorker`

## 3. app.py — wiring

- [x] 3.1 Remove the `TraxusApp.AudioFrame` message class
- [x] 3.2 Remove the `on_traxus_app_audio_frame` message handler
- [x] 3.3 Pass `audio_engine=self._audio_engine` when constructing `WsWorker` in `connect_to_server`
- [x] 3.4 Replace the `capture_loop` worker start with `self._audio_engine.set_send_target(self._ws_worker._binary_send_queue, channel)` when PTT transmission begins
- [x] 3.5 Call `self._audio_engine.set_send_target(None, "")` wherever PTT transmission ends (toggle off, hold release, VAD stop, disconnect)
- [x] 3.6 Remove any remaining imports or references to `capture_loop`

## 4. Server — concurrent relay

- [x] 4.1 In `MessageRouter.relay_voice`, replace the sequential `for` loop with `asyncio.gather(*[vc.ws.send(s2c_frame) for vc in receivers], return_exceptions=True)`

## 5. Tests

- [x] 5.1 Update `test_app.py`: remove any tests for `AudioFrame` message class or `on_traxus_app_audio_frame`
- [x] 5.2 Update `test_audio_engine.py`: remove tests for `capture_loop`; add tests for `set_send_target` (sets/clears queue and channel)
- [x] 5.3 Add test: capture callback posts packed frame to `_send_queue` when `_transmitting` and send target is set
- [x] 5.4 Add test: capture callback posts nothing when send target is `None`
- [x] 5.5 Update `test_message_router.py`: verify `relay_voice` sends to all receivers even when one raises
- [x] 5.6 Run full test suite and confirm all tests pass

## 6. End-to-end LAN latency test

- [x] 6.1 Create `tests/test_audio_pipeline_latency.py` with a class `TestAudioPipelineLatency(unittest.IsolatedAsyncioTestCase)` that spins up a real server subprocess (same pattern as `test_ptt_e2e.py`) and tears it down in `setUpClass`/`tearDownClass`
- [x] 6.2 Implement helper `_connect_client(username)` that connects a bare `WsWorker` + `AudioEngine` pair to the server, authenticates, creates and joins a voice channel named `"latency-test"`, and returns `(worker, engine)`
- [x] 6.3 Implement `test_lan_pipeline_latency`: connect a sender client and a receiver client; on the receiver patch `AudioEngine.play()` to record `time.perf_counter()` at the moment each frame is received; on the sender inject 50 synthetic raw-PCM frames (320 int16 samples of silence) directly into `_binary_send_queue`, recording `time.perf_counter()` immediately before each enqueue; collect per-frame latency as `t_play - t_enqueue`
- [x] 6.4 In `test_lan_pipeline_latency` assert: median latency < 15 ms, p95 < 30 ms, p99 < 50 ms; print a summary line `LATENCY  median={:.1f}ms  p95={:.1f}ms  p99={:.1f}ms` so it is visible in verbose test output
- [x] 6.5 Add a second assertion: zero frames dropped (all 50 injected frames reach `play()`) to confirm the pipeline is lossless under no-load LAN conditions
