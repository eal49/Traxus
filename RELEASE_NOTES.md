## What's new in v0.2.0

- **WebRTC audio (P2P)** — voice travels directly between clients via aiortc +
  Opus. The server handles only WebRTC signalling (offer/answer/ICE); no audio
  data ever touches the server.
- **MicTrack / PeerManager / RemoteAudioSink** — new modules replace the old
  binary-relay pipeline end-to-end.
- **Per-user volume** — keyboard controls (←/→) in the member panel adjust each
  participant's playback gain (0–200 %).
- **Noise suppression removed** — the spectral suppressor has been removed from
  the capture path. Opus handles the signal pipeline; the settings toggle is
  gone.
- **`/audioTest` command** — runs a loopback audio verification on the current
  voice channel.
- **Release `.exe` now includes WebRTC** — `aiortc` and `av` (PyAV) are bundled
  into the Windows executable; no extra install required for voice.

## Breaking changes

- **Binary audio relay removed** — v0.1.x clients and servers are not voice-
  compatible with this release. Text chat still works across versions.
- `shared/adpcm.py` and `shared/voice_protocol.py` have been removed.
- `AudioEngine.noise_suppression_enabled`, `AudioEngine.transmitting`, and the
  `noise_suppression` settings key no longer exist.
- `client/settings.json` entries for `noise_suppression` are silently ignored.
