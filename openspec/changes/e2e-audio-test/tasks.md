## 1. Headless Audio Client Script

- [x] 1.1 Create `tests/audio_client.py` with `argparse` entry point accepting `--role sender|receiver`, `--channel`, `--username`, `--output`, `--server` (default `ws://localhost:8765`)
- [x] 1.2 Implement `mock_sounddevice()` helper that patches `sounddevice.InputStream` with a `MagicMock` and returns a capturing mock for `sounddevice.OutputStream` (list of written byte chunks)
- [x] 1.3 Implement `auth_and_join(ws, username, channel)` coroutine: send `auth`, drain messages until `auth_ok`, send `vcreate` (ignore channel-exists error), send `voice_join`, drain messages until `voice_state` contains local user, return the `voice_state` users list
- [x] 1.4 Implement `run_signaling_loop(ws, peer_manager, local_username, done_event)` coroutine: loop over incoming WebSocket messages, dispatch `voice_state` → connect if `local < remote`, dispatch `voice_offer` → `peer_manager.on_offer`, `voice_answer` → `peer_manager.on_answer`, `voice_ice` → `peer_manager.on_ice`; stop when `done_event` is set
- [x] 1.5 Implement `sender_main(args)` coroutine: call `mock_sounddevice()`, connect websocket, call `auth_and_join`, create `PeerManager` with `iceServers=[]`, start signaling loop task, wait 3 s for ICE to establish, call `mic_track.set_transmitting(True)`, inject 100 frames of 440 Hz int16 PCM (320 samples each) into `mic_track._queue`, sleep 2 s to allow delivery, set `done_event`
- [x] 1.6 Implement `receiver_main(args)` coroutine: call `mock_sounddevice()` with OutputStream capture, connect websocket, call `auth_and_join`, create `PeerManager`, start signaling loop task, sleep 7 s (3 s ICE + 2 s audio + 2 s buffer), write all captured PCM bytes to `args.output`, set `done_event`
- [x] 1.7 Add `if __name__ == "__main__"` block: parse args, run appropriate coroutine with `asyncio.run()`

## 2. E2E Test File

- [x] 2.1 Create `tests/test_audio_e2e.py` importing `WEBRTC_AVAILABLE` from `client.audio_engine`; decorate the test class with `@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/sounddevice/numpy not installed")`
- [x] 2.2 Implement `setUpClass` / `tearDownClass` matching `test_ptt_e2e.py`: start `python -m server.main` subprocess, sleep 1.5 s; terminate and wait in teardown
- [x] 2.3 Implement `test_audio_flows_sender_to_receiver`: create a `tempfile.NamedTemporaryFile` for receiver output, launch sender subprocess (`python tests/audio_client.py --role sender ...`) and receiver subprocess (`python tests/audio_client.py --role receiver --output <tmp> ...`) via `subprocess.Popen`
- [x] 2.4 Wait for both subprocesses with a 20-second timeout using `proc.wait(timeout=20)`; on `TimeoutExpired`, kill both and `self.fail(f"{role} subprocess timed out")`
- [x] 2.5 Assert both processes exited with code 0; assert the output file is non-empty; read the file as `numpy.frombuffer(data, dtype=numpy.int16)`, compute RMS, assert `rms > 100`

## 3. Verification

- [x] 3.1 Run `python -m unittest tests.test_audio_e2e -v` in isolation and confirm the test passes (green)
- [x] 3.2 Run the full suite `python -m unittest discover -s tests -v` and confirm all existing tests still pass (no regressions)
