## 1. Settings

- [x] 1.1 Add `jitter_buffer_frames` key (default `3`) to `_DEFAULTS` in `client/settings.py`

## 2. AudioEngine — overflow fix

- [x] 2.1 In `AudioEngine.play()`, replace the drop-oldest logic with drop-newest: discard the incoming frame when `_play_queue` is full instead of removing the oldest item
- [x] 2.2 Add `_jitter_buffer_frames: int` attribute to `AudioEngine.__init__`, reading from a `jitter_buffer_frames` parameter (default `3`)

## 3. AudioEngine — jitter buffer in playback worker

- [x] 3.1 In `_playback_worker`, open `sd.OutputStream` with `latency="low"`
- [x] 3.2 Add a pre-fill gate: before the drain loop, block on `_play_queue.get()` until `_jitter_buffer_frames` frames are accumulated in a local list
- [x] 3.3 Implement the 20 ms clock drain loop using `time.perf_counter` for `next_tick` scheduling: sleep `max(0, next_tick - time.perf_counter())` before each `out_stream.write()`, then advance `next_tick` by `_FRAME_SECONDS`
- [x] 3.4 On queue underrun (timeout), reset to pre-fill gate (wait silently until buffer re-primes)
- [x] 3.5 Add module-level constant `_FRAME_SECONDS = _BLOCKSIZE / _SAMPLERATE` (= 0.02)

## 4. Wire up setting to AudioEngine

- [x] 4.1 In `client/app.py`, pass `jitter_buffer_frames` from loaded settings to `AudioEngine` constructor (or add a setter and call it after settings load)

## 5. Tests

- [x] 5.1 Update `test_audio_engine.py`: verify `play()` does not raise and discards the new frame (not an old one) when the queue is full
- [x] 5.2 Add test: verify `AudioEngine` reads `jitter_buffer_frames` from constructor argument and stores it as `_jitter_buffer_frames`
- [x] 5.3 Add test: verify `settings.py` default includes `jitter_buffer_frames: 3`
- [x] 5.4 Run full test suite and confirm all tests pass
