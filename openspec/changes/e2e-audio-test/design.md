## Context

The Traxus audio pipeline is WebRTC P2P: two clients exchange SDP offer/answer and ICE candidates through the WebSocket server, then audio flows directly between them via DTLS-SRTP. The existing test suite covers signaling state (PTT key, voice_state message) but never verifies that audio bytes actually arrive at the far end.

The pipeline under test:

```
Sender (alice)                    Server (relay)            Receiver (bob)
──────────────────────────────    ──────────────────────    ──────────────────────────────
MicTrack._queue ← inject PCM
MicTrack.recv() → av.AudioFrame
aiortc RTPSender [Opus encode]
  ──── DTLS-SRTP (loopback) ──────────────────────────────▶ aiortc RTPReceiver [Opus decode]
                                                            on_track() → RemoteAudioSink
                                                            out_stream.write(pcm) ← capture
```

Signaling (offer/answer/ICE) flows through the server WebSocket relay. Audio is P2P on loopback once ICE connects.

## Goals / Non-Goals

**Goals:**
- Verify that audio bytes sent by the sender actually reach the receiver with non-trivial energy (not silence)
- Run headlessly in CI with no audio hardware
- Complete in under 20 seconds
- Reuse production `PeerManager`, `MicTrack`, `RemoteAudioSink` without modification

**Non-Goals:**
- Testing frequency accuracy or codec fidelity (Opus is lossy; RMS threshold is sufficient)
- Testing the Textual TUI layer (covered by the rest of the test suite)
- Testing with multiple simultaneous voice participants (two-party is sufficient to validate the pipeline)
- STUN/TURN traversal (loopback ICE only)

## Decisions

### D1 — Separate OS processes for each client

**Decision:** Run sender and receiver as separate `subprocess.Popen` processes using a shared `tests/audio_client.py` entry point with a `--role` flag.

**Rationale:** Each process gets its own asyncio event loop and its own Python interpreter state. This eliminates all contention between two Textual/asyncio apps and mirrors exactly how a user runs two terminal windows. `test_ptt_e2e.py` already validates this pattern for the server.

**Alternative considered:** Two `asyncio.Task` coroutines in the same process. Rejected because Textual owns the event loop and running two `App.run_test()` contexts concurrently is unsupported.

---

### D2 — Headless async script, not a full TraxusApp

**Decision:** `tests/audio_client.py` uses raw `websockets.connect()` + `PeerManager` directly, with no Textual dependency.

**Rationale:** The audio path (`MicTrack → WebRTC → RemoteAudioSink`) does not go through the TUI. Skipping Textual removes ~400 ms startup time per client and eliminates screen-render noise. The signaling dispatch that app.py provides (routing voice_offer/answer/ICE to peer_manager) is replicated as a compact `_dispatch()` coroutine in the script.

**Alternative considered:** Full `TraxusApp` subprocesses driven via `pexpect`. Rejected: fragile, platform-specific, adds a heavy dependency.

---

### D3 — Empty ICE server list for loopback

**Decision:** Both clients use `RTCConfiguration(iceServers=[])`, disabling STUN/TURN entirely.

**Rationale:** Both peers run on the same machine. Host candidates (`127.0.0.1`) are sufficient for loopback. Removing the STUN lookup eliminates the 1–3 s timeout that occurs when `stun.l.google.com` is unreachable in CI.

**Alternative considered:** Mocking the STUN server. Rejected: unnecessary complexity when loopback host candidates are guaranteed to work.

---

### D4 — Lexicographic offer/answer role assignment

**Decision:** The sender (`alice`) always makes the WebRTC offer because `"alice" < "bob"`. This is consistent with the fix already applied in `app.py`.

**Rationale:** Prevents the dual-offer glare condition that was the original audio bug. The test script enforces the same rule: only call `peer_manager.connect(remote)` if `local_username < remote_username`.

---

### D5 — sounddevice.InputStream mocked; OutputStream captured via side_effect

**Decision:** In the sender process, `sounddevice.InputStream` is replaced with a `MagicMock` before `MicTrack` is constructed (so no real mic is opened). Audio is injected directly into `MicTrack._queue`. In the receiver process, `sounddevice.OutputStream` is replaced with a mock whose `write` side-effect appends bytes to a list that is flushed to a file on exit.

**Rationale:** CI machines have no audio hardware. Both mocks are applied at the `client.mic_track` / `client.peer_manager` import level so they intercept construction before any real device is opened.

---

### D6 — Audio verification: RMS energy threshold

**Decision:** The test asserts `rms(received_pcm) > 100` (out of 32767 max). This is the only correctness criterion.

**Rationale:** Opus introduces lossy compression and resampling; bit-exact comparison is not meaningful. An RMS floor of 100 (~0.3% of full scale) reliably distinguishes a 440 Hz tone (RMS ≈ 13000) from silence (RMS = 0) with wide margin. Frequency analysis would be more rigorous but adds complexity without catching real bugs that a simple energy check would miss.

---

### D7 — Receiver output via temp file, sender exit signals completion

**Decision:** The receiver writes captured PCM to a path passed as `--output <path>`. The test waits for both subprocesses to exit (with a timeout), then reads the file.

**Rationale:** Inter-process communication via the filesystem is the simplest, most debuggable option. No pipes, no sockets, no shared memory.

## Risks / Trade-offs

- **ICE timing on slow CI** → The test allows 10 s for ICE establishment + 2 s for audio delivery. If the machine is heavily loaded, ICE may take longer. Mitigation: the 10 s budget is generous for loopback; increase timeout constants if CI flakes.
- **aiortc compatibility with Python 3.14** → aiortc depends on pyOpenSSL and cryptography. If these have issues on 3.14, the test will skip with a clear import error rather than fail. Mitigation: wrap the test class with `@unittest.skipUnless(WEBRTC_AVAILABLE, ...)`.
- **Port conflict on 8765** → The server subprocess uses the default port. If another process holds it, the test fails at connection. Mitigation: same risk exists in `test_ptt_e2e.py`; acceptable.
- **Opus fidelity** → Opus at 16 kHz mono is tuned for voice; a 440 Hz sine might be attenuated slightly. The RMS threshold of 100 is well below expected ~13000, providing ample margin.

## Open Questions

- None — design is fully specified.
