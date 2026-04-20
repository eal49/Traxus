## Why

The WebRTC audio pipeline has no automated end-to-end test that verifies audio actually flows between two connected clients. Regressions (such as the dual-offer glare bug) are only caught manually, making audio quality a persistent blind spot in CI.

## What Changes

- Add `tests/audio_client.py` — a headless async client script (no Textual) that runs as a subprocess in `--role sender` or `--role receiver` mode, exercising the real WebSocket + PeerManager + MicTrack + RemoteAudioSink pipeline.
- Add `tests/test_audio_e2e.py` — a `unittest.TestCase` that starts the server subprocess, launches both client subprocesses, and asserts the receiver captured non-silent audio.
- No changes to production code.

## Capabilities

### New Capabilities

- `e2e-audio-verification`: Headless two-process audio integration test that connects two clients to a live server, sends a known tone from one, and asserts the other receives non-silent audio via WebRTC.

### Modified Capabilities

<!-- none -->

## Impact

- New files: `tests/audio_client.py`, `tests/test_audio_e2e.py`
- Reuses: `client/peer_manager.py`, `client/mic_track.py`, `client/remote_audio_sink.py`, `shared/message_types.py`
- Dependencies exercised: `aiortc`, `websockets`, `numpy`, `sounddevice` (InputStream mocked, OutputStream captured)
- Test runtime: ~15 seconds (ICE establishment + 2 s audio + teardown)
