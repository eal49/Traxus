## 1. AudioMixer — new class

- [x] 1.1 Create `client/audio_mixer.py` with `AudioMixer.__init__`: accepts `sd.OutputStream`, starts internal `run()` task via `asyncio.ensure_future`
- [x] 1.2 Implement `AudioMixer.add_user(username)` — creates a bounded `asyncio.Queue` slot (max 20 frames)
- [x] 1.3 Implement `AudioMixer.remove_user(username)` — discards the queue slot
- [x] 1.4 Implement `AudioMixer.push(username, pcm: np.ndarray)` — non-blocking `put_nowait`, drop on overflow
- [x] 1.5 Implement `AudioMixer.run()` — timer-driven 20 ms loop: dequeue one frame per active user (silence if empty), sum as float32, clip to int16, `run_in_executor` write; use absolute target timestamps to prevent drift (same pattern as `MicTrack.recv`)
- [x] 1.6 Implement `AudioMixer.restart_output_stream(device)` — open-swap-wait-close (port from `PeerManager.restart_output_stream`)
- [x] 1.7 Implement `AudioMixer.close()` — cancel task, await it, stop/close OutputStream

## 2. RemoteAudioSink — adapt to push instead of write

- [x] 2.1 Change `RemoteAudioSink.__init__` signature: replace `out_stream_holder: list` with `mixer: AudioMixer`
- [x] 2.2 In `RemoteAudioSink.run()`: after volume gain, call `self._mixer.push(self._username, pcm)` instead of `run_in_executor(stream.write, pcm)`
- [x] 2.3 Remove the `run_in_executor` write and the `stream` local variable from `RemoteAudioSink.run()`

## 3. PeerManager — wire AudioMixer

- [x] 3.1 Add `AudioMixer` import and construction in `PeerManager.__init__`: replace `_out_stream` / `_out_stream_holder` fields with `_mixer: AudioMixer`
- [x] 3.2 In `PeerManager.connect()` and `PeerManager.on_offer()`: call `self._mixer.add_user(username)` before creating the peer connection
- [x] 3.3 In `PeerManager.disconnect()`: call `self._mixer.remove_user(username)` after cancelling the sink task
- [x] 3.4 In `PeerManager._create_pc()` `on_track` handler: pass `self._mixer` to `RemoteAudioSink` instead of `self._out_stream_holder`
- [x] 3.5 Replace `PeerManager.restart_output_stream` with a delegation to `self._mixer.restart_output_stream`
- [x] 3.6 In `PeerManager.close_all()`: call `await self._mixer.close()` instead of manually stopping the stream

## 4. app.py — construction update

- [x] 4.1 In `_handle_voice_state_webrtc`: open the `sd.OutputStream` then pass it to `AudioMixer` constructor; pass the `AudioMixer` to `PeerManager` (not the raw stream)
- [x] 4.2 Remove direct `out_stream` reference from `PeerManager` construction call

## 5. Tests — existing suite

- [x] 5.1 Update `tests/test_remote_audio_sink.py`: replace `out_stream_holder` fixture with a mock `AudioMixer`; verify `push()` is called with correct PCM and volume-adjusted PCM
- [x] 5.2 Update `tests/test_peer_manager.py`: replace stream mock with `AudioMixer` mock; verify `add_user`/`remove_user` calls on connect/disconnect; verify `restart_output_stream` delegates to mixer
- [x] 5.3 Run full test suite — confirm all existing tests pass before adding new ones

## 6. Tests — AudioMixer

- [x] 6.1 Create `tests/test_audio_mixer.py` with `IsolatedAsyncioTestCase`
- [x] 6.2 Test: no users → mixer writes silence frame each tick
- [x] 6.3 Test: single user → mixer output equals that user's pushed frame (with volume 100)
- [x] 6.4 Test: two users → mixer output equals float32 sum clipped to int16
- [x] 6.5 Test: two users where sum exceeds int16 range → output is clipped, no overflow
- [x] 6.6 Test: user slot with no queued frame (missing frame) → mixer fills with silence, does not stall
- [x] 6.7 Test: `add_user` then `remove_user` → removed user's frames no longer appear in mixer output
- [x] 6.8 Test: `close()` cancels the internal task cleanly, no exception raised
