## ADDED Requirements

### Requirement: Headless audio client script

The test suite SHALL include `tests/audio_client.py`, a self-contained async script with no Textual dependency that connects to a running Traxus server, authenticates, joins a voice channel, and either sends or receives audio depending on `--role`.

#### Scenario: Sender mode injects known audio

- **WHEN** the script is invoked with `--role sender --channel <ch> --username alice`
- **THEN** it connects to the server, authenticates as alice, creates the voice channel if absent, joins it, creates a PeerManager with an empty ICE server list, sets `transmitting=True`, injects 100 frames of 440 Hz 16-bit PCM directly into `MicTrack._queue`, waits for all frames to be consumed, then exits with code 0

#### Scenario: Receiver mode captures audio to file

- **WHEN** the script is invoked with `--role receiver --channel <ch> --username bob --output <path>`
- **THEN** it connects to the server, authenticates as bob, joins the voice channel, creates a PeerManager, intercepts `sounddevice.OutputStream.write` calls from `RemoteAudioSink`, accumulates the raw int16 PCM bytes, writes them to `<path>` on exit, then exits with code 0

#### Scenario: sounddevice hardware is not required

- **WHEN** no real audio device is present on the host
- **THEN** `sounddevice.InputStream` SHALL be replaced with a no-op mock before `MicTrack` is constructed, and `sounddevice.OutputStream` SHALL be replaced with a capturing mock before `PeerManager` is constructed, so the script completes without error

#### Scenario: ICE uses loopback only

- **WHEN** a PeerManager is created by the script
- **THEN** it SHALL use `RTCConfiguration(iceServers=[])` so no STUN lookup is attempted and ICE candidates are limited to `127.0.0.1` host candidates

---

### Requirement: E2E audio integration test

The test suite SHALL include `tests/test_audio_e2e.py` containing a `unittest.TestCase` that verifies audio flows end-to-end between two headless client subprocesses.

#### Scenario: Test setup starts a server subprocess

- **WHEN** `setUpClass` runs
- **THEN** it SHALL start `python -m server.main` as a subprocess and wait 1.5 s for it to bind, matching the pattern in `test_ptt_e2e.py`

#### Scenario: Audio flows from sender to receiver

- **WHEN** the test method runs sender and receiver subprocesses concurrently against the same server
- **THEN** both subprocesses SHALL exit with code 0 within 20 seconds, and the output file written by the receiver SHALL exist and be non-empty

#### Scenario: Received audio is non-silent

- **WHEN** the receiver output file is read as raw int16 PCM
- **THEN** its RMS energy SHALL exceed 100 (out of 32767 maximum), confirming that real audio — not silence — was received via WebRTC

#### Scenario: Test skips when aiortc is unavailable

- **WHEN** `aiortc` cannot be imported in the test process
- **THEN** the test class SHALL be decorated with `@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not installed")` so it is skipped rather than erroring

#### Scenario: Subprocess timeout is enforced

- **WHEN** either subprocess does not exit within 20 seconds
- **THEN** the test SHALL terminate both subprocesses and fail with a descriptive message indicating which role timed out

---

### Requirement: Signaling dispatch in headless client

The headless client SHALL implement a compact signaling dispatcher that routes `voice_offer`, `voice_answer`, and `voice_ice` server messages to the local `PeerManager`, replicating the subset of `app.py` message handling needed for WebRTC negotiation.

#### Scenario: Offer is dispatched to PeerManager

- **WHEN** the server relays a `voice_offer` message to the headless client
- **THEN** the dispatcher SHALL call `peer_manager.on_offer(from_user, sdp)` and the client SHALL respond with a `voice_answer` sent through the WebSocket

#### Scenario: Answer is dispatched to PeerManager

- **WHEN** the server relays a `voice_answer` message to the headless client
- **THEN** the dispatcher SHALL call `peer_manager.on_answer(from_user, sdp)` to complete the SDP handshake

#### Scenario: ICE candidates are dispatched to PeerManager

- **WHEN** the server relays a `voice_ice` message to the headless client
- **THEN** the dispatcher SHALL call `peer_manager.on_ice(from_user, candidate, sdpMid, sdpMLineIndex)`

#### Scenario: Lexicographic offer rule is enforced

- **WHEN** the headless client receives a `voice_state` update containing a remote peer
- **THEN** it SHALL call `peer_manager.connect(remote_username)` only if `local_username < remote_username`, preventing dual-offer glare
