## What's new in v0.2.6

- **Multi-peer voice fixed** — audio is now intelligible when 3 or more clients
  share a voice channel. Previously each `RemoteAudioSink` wrote PCM directly to
  a shared `sd.OutputStream` from concurrent executor threads; PortAudio
  serialised the writes instead of mixing them, producing choppy round-robin
  playback or silence. A new `AudioMixer` class is now the sole writer: it
  collects decoded frames from all remote participants in per-user queues, sums
  them with float32 accumulation (clipped to int16), and performs exactly one
  `OutputStream.write()` call every 20 ms — regardless of how many speakers are
  active.

## What's new in v0.2.5

- **Slash-command history** — Up/Down arrows in the input bar cycle through
  previously submitted slash commands, bash-style. History is persisted to
  `~/.config/traxus/command_history.json` across restarts, capped at 200
  entries, with consecutive-duplicate suppression. Plain chat messages are
  excluded. The current draft is saved and restored when navigating back.
- **Tab completion for slash commands** — Tab cycles forward through command
  names matching the current prefix; Shift+Tab cycles backward. Single match
  completes immediately. Escape restores the original prefix. No trailing space
  is inserted, avoiding accidental triggering of `/quote` / `/pin` selection mode.
- **Polished GitHub landing page** — README now has a centered hero logo,
  shields.io badges (Python 3.14+, platform, test count), and emoji section
  headers for scannability. Stale content fixed: removed non-existent
  `voice_protocol.py` and `PttKeyScreen` from the structure table, added
  `ColorPickerScreen`, `DeviceSelectScreen`, and `VadSensitivityScreen`,
  and updated the Python version requirement to 3.14+.

## What's new in v0.2.4

- **VAD mode no longer breaks after changing the sensitivity threshold** — opening
  `/settings → VAD Sensitivity` and pressing Enter or Escape now reliably restarts
  the mic stream so VAD continues detecting voice when you return to the channel.
  Previously the stream was closed by the calibration screen but never reopened
  (cancel path) or restarted synchronously and silently failed on WASAPI (save path).
  The restart is now async with a short driver-release delay.
- **PTT key is a no-op in VAD mode** — pressing F9 (or the configured PTT key /
  mouse button) while in VAD mode no longer accidentally toggles transmission; VAD
  remains the sole gate for starting and stopping audio.

## What's new in v0.2.3

- **`/vleave` now works when others are in the channel** — previously, leaving a
  voice channel while other participants remained would silently fail: WebRTC
  connections stayed open, the UI kept showing the user as connected, and PTT
  stayed armed. The server now sends an empty `users` list to the leaving client
  so it always tears down cleanly regardless of remaining participants.

## What's new in v0.2.2

- **Audio device selection** — choose input and output devices from Settings.
  The selection persists across sessions and hot-swaps while in a voice channel
  without requiring a rejoin.
- **Device hot-swap no longer freezes the UI** — all PortAudio stream
  open/close and `sd.OutputStream.write()` calls now run off the asyncio event
  loop thread. Changing devices mid-call is smooth with at most a brief silence.
- **Device picker opens instantly** — device enumeration runs in a background
  worker so the list never blocks the UI.

## What's new in v0.2.1

- **CI fix** — `libportaudio2` is now installed on the Ubuntu test runner before
  `sounddevice`, resolving an `OSError: PortAudio library not found` import
  failure that caused all audio-related tests to fail in CI.

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
