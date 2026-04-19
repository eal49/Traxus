## What's new

- **WebRTC audio** — voice is now transported peer-to-peer over WebRTC (aiortc)
  instead of being relayed as binary frames through the server. Audio no longer
  touches the server after the initial WebRTC handshake, eliminating server
  bandwidth and relay latency entirely.
- **WebRTC signaling** — the server relays `voice_offer`, `voice_answer`, and
  `voice_ice` JSON messages to set up peer connections. Once ICE completes,
  audio flows directly between clients.
- **MicTrack** — new `client/mic_track.py` bridges sounddevice microphone
  capture into a WebRTC `AudioStreamTrack`. Silence frames are emitted when PTT
  is inactive; real PCM frames when transmitting.
- **RemoteAudioSink** — new `client/remote_audio_sink.py` reads decoded PCM
  from a remote WebRTC track and writes to the shared `sd.OutputStream` with
  per-user volume gain applied.
- **PeerManager** — new `client/peer_manager.py` manages the full lifecycle of
  `RTCPeerConnection` objects: creating offers, handling answers, adding ICE
  candidates, and tearing down connections on voice leave.
- **Spectral noise suppression** retained — `_SpectralNoiseSuppressor` still
  runs in the microphone callback before PCM is handed to MicTrack.
- **Per-user volume** — moved from `AudioEngine` to `PeerManager`; keyboard
  controls in `MemberPanel` (←/→ arrows) work as before.

## Bug fixes

- Loopback playback removed from `MicTestScreen` (not possible in WebRTC
  pipeline); UI shows "Loopback: Off (audio is WebRTC)" instead of toggling.

## Breaking changes

- **Binary audio relay removed** — Traxus no longer sends or receives WebSocket
  binary frames for audio. Servers and clients from v0.1.x are not compatible
  with this release for voice channels.
- `shared/voice_protocol.py` and `shared/adpcm.py` have been deleted.
- `AudioEngine.play()`, `set_send_target()`, and `_playback_worker` have been
  removed. Code that calls these methods must be updated.
- `AudioEngine.__init__` no longer accepts a `jitter_buffer_frames` parameter.
- Per-user volume is now managed by `PeerManager.get_volume()` /
  `set_volume()`, not `AudioEngine`.
