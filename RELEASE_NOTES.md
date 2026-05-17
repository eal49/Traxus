## What's new in v0.3.4

- **Discord-like member panel** — the right panel now shows a server-wide
  **Online** and **Offline** roster instead of a channel-scoped list. Every
  known user appears the moment they authenticate; voice-active users display
  a volume icon (🔇/🔈/🔉/🔊) and percentage, with ←/→ volume adjustment
  unchanged. Offline members are shown dimmed below an **OFFLINE — N** header.
- **Voice channel member nesting** — the left sidebar now lists the current
  occupants of each voice channel as non-interactive rows indented under the
  channel name, so you can see who is in which channel without joining.
- **Global presence events** — the server broadcasts `user_online` when a
  client authenticates and `user_offline` when one disconnects. The `auth_ok`
  response now includes `online_users` (currently connected) and `known_users`
  (all registered accounts) so the roster is accurate from the first frame.
- **`voice_members` in channel_list** — every `channel_list` message now
  includes a `voice_members` array for each voice channel; the list is
  rebroadcast to all clients on every voice join, leave, or disconnect.

## What's new in v0.3.3

- **+6 dB global receive boost** — all remote voice audio is now amplified by
  2× before per-participant volume scaling is applied. Raw Opus output sits
  around −20 dBFS; most games and applications master audio at −6 to −12 dBFS.
  The flat +6 dB lift closes that gap without touching the existing per-user
  volume slider semantics. Users who have already calibrated individual volumes
  will not notice any change in relative balance.
- **Opus bandwidth optimisations** — every outgoing SDP offer and answer now
  injects DTX (`usedtx=1`), in-band FEC (`useinbandfec=1`), and a 16 kbps
  average-bitrate cap (`maxaveragebitrate=16000`) into the Opus `a=fmtp` line.
  DTX reduces near-silent packets to near zero; FEC provides frame-loss
  resilience at minimal overhead; the bitrate cap halves the default 32 kbps
  Opus encoder rate while preserving clear voice quality.

## What's new in v0.3.1

- **System tray icon** — a tray icon now reflects your live connection and PTT
  state at a glance, even when the terminal is minimised. Six states are shown:
  Disconnected, Connected, Voice Connected, Listening (VAD monitoring), Speaking,
  and Speaking & Listening (transmitting while others are present). Requires
  `pystray>=0.19` and `Pillow>=9.0`; both are bundled in the `.exe` and macOS
  binary. Install separately for source runs: `pip install pystray Pillow`. On
  Windows the icon may appear in the notification overflow (`^` arrow) on first
  run — drag it to the visible taskbar area to pin it.
- **User guide** — a new end-user manual at `docs/user-guide.md` covers
  installation, the interface, text chat, voice channels, settings, the system
  tray, all slash commands, and keyboard shortcuts.
- **Documentation cleanup** — all references to a specific DuckDNS subdomain
  replaced with generic `yourdomain.example.com` placeholders throughout docs,
  deploy guides, login screen placeholder, and release notes.

## What's new in v0.3.0

- **Password authentication** — servers can now require a password to connect.
  Set `TRAXUS_USERS=/home/ubuntu/Traxus/users.json` in the systemd service and
  create accounts with `python -m server.adduser <username>`. The login screen
  gains an optional **Password** field; servers without auth ignore it entirely.
  Credentials are bcrypt-hashed (work factor 12); the file is never readable by
  the client. See `deploy/deploy.md` for the full setup guide.
- **Fix: macOS and Windows clients now connect via `wss://`** — PyInstaller
  builds were missing the CA certificate bundle needed for TLS verification.
  `wss://` connections silently failed; this is now fixed by bundling
  `certifi`'s CA store into the executable.

## What's new in v0.2.9

- **macOS Apple Silicon binary** — a self-contained arm64 executable is now
  published with every release (`traxus-vX.Y.Z-macos-arm64`). No Python
  installation required. On first launch, clear Gatekeeper's quarantine flag:
  `xattr -rd com.apple.quarantine ./traxus-*-macos-arm64 && chmod +x ./traxus-*-macos-arm64`
  Then run from Terminal.app or iTerm2. Intel Macs are not supported by this
  binary; use `pip install` from source instead.
- **PTT fade-in** — the first audio frame after pressing Push-to-Talk now ramps
  from silence to full amplitude over 20 ms, eliminating the audible pop that
  occurred when the microphone gate opened mid-sample. Subsequent frames play at
  full amplitude immediately. The fade is applied to both `MicTrack` (single
  peer) and `MicFork` (multi-peer fan-out).
- **AGPL v3 license** — the repository is now licensed under the GNU Affero
  General Public License v3. Anyone running a modified version of the Traxus
  server must publish their changes.

## What's new in v0.2.8

- **Perceptual volume curve** — the per-participant volume slider now uses a
  squared power-law gain curve (`gain = (level / 100) ** 2`) instead of a
  linear one. At 200 % the boost is +12 dB (4×) rather than +6 dB (2×), and
  at 50 % the cut is −12 dB (0.25×) rather than −6 dB (0.5×). The curve is
  symmetric in log-space around unity: 50 % is now the true perceptual inverse
  of 200 %, matching how human hearing experiences loudness. The 100 % fast-path
  (no multiply) is preserved.

## What's new in v0.2.7

- **Multi-peer microphone fan-out fixed** — audio sent by a local client is now
  correctly delivered to every remote participant when 3 or more clients share a
  voice channel. Previously the same `MicTrack` object was added to every
  `RTCPeerConnection`; aiortc's per-connection encoding coroutines called
  `recv()` concurrently on the shared object, causing frames to be split between
  connections and the PTS counter to advance at N× the correct rate. Each
  connection now gets its own `MicFork` — an independent `AudioStreamTrack` with
  a separate queue and PTS counter — so every peer receives a complete,
  correctly-timestamped copy of the microphone stream.
- **AudioMixer mixing proved correct** — a new 3-client end-to-end test starts
  a real server, an alice sender (440 Hz), a bob sender (880 Hz), and a charlie
  receiver, then FFT-verifies that charlie's captured audio contains energy at
  both 440 Hz and 880 Hz simultaneously, proving the mixer sums all active
  speakers without losing any stream.

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
