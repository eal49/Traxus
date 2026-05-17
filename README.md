<div align="center">

<img src="Art/HX1vx.jpg" width="480" alt="Traxus">

# TRAXUS

*Real-time text and voice chat — entirely in your terminal.*

![Python](https://img.shields.io/badge/python-3.14%2B-blue?style=flat)
![Platform](https://img.shields.io/badge/platform-Linux%20%C2%B7%20macOS%20%C2%B7%20Windows-lightgrey?style=flat)
![Tests](https://img.shields.io/badge/tests-617%20passing-brightgreen?style=flat)

</div>

```
┌─────────────────────────────────────────────────────────────────────┐
│ Traxus                                          alice @ #general    │
├──────────────┬──────────────────────────────────────────────────────┤
│ TEXT          │ [10:42] alice   hey, anyone around?                  │
│  # general   │ [10:42] bob     yep — just finished the build        │
│  # dev       │ [10:43] carol   joining dev-voice now                │
│              │ [10:43] alice   on my way                            │
│ VOICE        │                                                       │
│  ◈ dev-voice │                                                       │
│    · bob     │                                                       │
│    · carol   │                                                       │
├──────────────┴──────────────────────────────────────────────────────┤
│ > /vjoin dev-voice                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ ws://localhost:8765  alice  ●  42 ms                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why Traxus?

| | Traxus | Discord / Slack |
|---|---|---|
| Runs in a terminal | ✓ | ✗ |
| Works over SSH | ✓ | ✗ |
| Self-hosted | ✓ | ✗ |
| Zero telemetry | ✓ | ✗ |
| Voice (WebRTC / Opus P2P) | ✓ | ✓ |
| Free forever | ✓ | Paywalled features |
| Open source | ✓ | ✗ |

---

## Features

### 💬 Text Chat
- Multiple channels — join, leave, create on the fly
- Scrolling message history with Rich-formatted output
- Per-channel member list (`/who`) with live presence updates
- Change your nick at any time (`/nick`)

### 🎙️ Voice
- **Peer-to-peer WebRTC audio** — voice goes directly between clients via
  aiortc + Opus; the server only handles signalling (offer/answer/ICE).
  No audio data ever touches the server.
- **Three PTT modes** via `/settings`:
  - `Toggle` — press F9 once to start, again to stop
  - `Hold` — hold F9 while speaking (hands-free release)
  - `VAD` — voice activity detection; mic opens automatically when you speak
- Live mic indicator in the status bar (`● MIC`)
- Per-user volume control (0–200 %) from the member panel
- VAD calibration screen with live energy bar chart and adjustable threshold
- Rebind PTT to any key or mouse button (middle-click recommended)
- **Audio device selection** — choose input and output devices from `/settings`;
  hot-swaps mid-call without requiring a rejoin, without freezing the UI
- Graceful degradation — all text features work without `sounddevice` or `aiortc`

### ⌨️ Terminal-native UX
- Keyboard-first — full slash command set, no mouse required
- Tab / Shift+Tab completes slash command names in the input bar
- Up / Down arrow recalls previously submitted slash commands
- Sidebar groups text and voice channels with live member counts
- Status bar: connection state, username, latency, PTT indicator
- Login (server URL + username) persists across restarts

### 🚀 Self-hostable in minutes
- Single asyncio WebSocket server, zero database, zero config files
- Deploy on any Ubuntu 24.04 VPS (Hetzner, OVH, Linode, …)
- TLS via Caddy + Let's Encrypt (any domain or free dynamic DNS subdomain)
- Optional password authentication — bcrypt-hashed credentials, enabled per-server
- Managed by systemd — see [deploy/deploy.md](deploy/deploy.md)

---

## Quick Start

```bash
# Install dependencies
pip install textual websockets

# Voice (optional — enables PTT, VAD, and WebRTC audio)
pip install sounddevice numpy aiortc av

# Terminal 1 — start the server
python -m server.main

# Terminal 2, 3, … — connect clients
python -m client.main
```

On the login screen enter `ws://localhost:8765`, pick a username, and press **Connect**.
If the server requires a password, fill in the **Password** field before connecting.

> **Python 3.14+** is required.

---

## Slash Commands

| Command | What it does |
|---|---|
| `/join <channel>` | Switch to a text channel |
| `/leave [channel]` | Leave a channel |
| `/create <name>` | Create a new text channel |
| `/vcreate <name>` | Create a new voice channel |
| `/vjoin <channel>` | Join a voice channel (enables PTT / VAD) |
| `/vleave` | Leave the current voice channel |
| `/nick <name>` | Change your display name |
| `/channels` | List all channels |
| `/who` | List members in the current channel |
| `/settings` | Open settings (PTT mode, PTT key, VAD sensitivity, audio devices) |
| `/audioTest` | Run a loopback audio test on the current voice channel |
| `/help` | Print command reference inline |
| `/quit` | Disconnect and exit |

**PTT** is bound to `F9` by default with priority over all widgets — it fires even
while you're typing. Change the binding or mode in `/settings`.

---

## Audio Pipeline

```
Microphone
    │  16 kHz · mono · int16 · 20 ms frames
    ▼
MicTrack (aiortc AudioStreamTrack)
    │  PCM frames queued at 20 ms wall-clock rate
    ▼
Opus encode          ← aiortc / libopus
    │
    ▼  RTP over ICE (peer-to-peer, no server relay)
    │
Opus decode          ← aiortc / libopus
    │  48 kHz stereo → mono · volume gain
    ▼
RemoteAudioSink      ← asyncio coroutine, writes to sd.OutputStream
```

Audio travels directly between peers — the server sees only WebSocket
signalling messages (SDP offer/answer and ICE candidates).

---

## Documentation

| Document | Description |
|---|---|
| [docs/user-guide.md](docs/user-guide.md) | End-user manual — connecting, text chat, voice, settings, system tray, shortcuts |
| [docs/commands.md](docs/commands.md) | Slash command reference — syntax, arguments, server effects, error conditions |
| [docs/protocol.md](docs/protocol.md) | Full WebSocket protocol — every C2S and S2C message type with field tables |
| [docs/server-rules.md](docs/server-rules.md) | Server business rules — auth, validation, broadcast scope, state invariants |
| [docs/architecture.md](docs/architecture.md) | Architecture deep-dive — audio pipeline, thread model, design decisions |

---

## Project Structure

```
traxus/
├── shared/                  # Zero-dependency protocol layer
│   └── message_types.py     # C2S / S2C / ErrorCode string constants + VERSION
├── server/                  # asyncio WebSocket server
│   ├── main.py              # Entry point, per-connection handler
│   ├── connection_manager.py
│   ├── channel_registry.py
│   ├── message_router.py    # Dispatches every C2S message type
│   ├── auth_store.py        # bcrypt credential store (optional password auth)
│   └── adduser.py           # CLI tool: python -m server.adduser <username>
├── client/                  # Textual TUI client
│   ├── app.py               # Root App, reactive state, PTT bindings
│   ├── ws_worker.py         # WebSocket recv / send / ping loops
│   ├── audio_engine.py      # VAD + energy callbacks + spectrum visualisation
│   ├── mic_track.py         # aiortc AudioStreamTrack fed by sounddevice
│   ├── peer_manager.py      # RTCPeerConnection lifecycle per remote peer
│   ├── remote_audio_sink.py # WebRTC track → volume gain → sd.OutputStream
│   ├── commands.py          # Slash command parser
│   ├── settings.py          # ~/.config/traxus/ persistence (settings + history)
│   ├── screens/             # LoginScreen, ChatScreen, SettingsScreen,
│   │                        # VadCalibrationScreen, VadSensitivityScreen,
│   │                        # MicTestScreen, ColorPickerScreen, DeviceSelectScreen
│   └── widgets/             # ChannelSidebar, MessageView, InputBar,
│                            # StatusBar, MemberPanel
├── tests/                   # unittest suite (606 tests)
├── docs/                    # Reference documentation
└── openspec/                # Feature specs and design artefacts
```

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

617 tests covering every server component, the full command parser, WebRTC
signalling, VAD modes, PTT hold/toggle/mouse, per-user volume, audio device
selection, password authentication, systray state logic, and end-to-end
integration tests with a real server subprocess and Textual pilot.

---

## Requirements

| Dependency | Required for |
|---|---|
| Python 3.14+ | Everything |
| `textual` | TUI client |
| `websockets` | Client + server |
| `certifi` | CA certificate bundle for `wss://` connections |
| `sounddevice` | Microphone capture + speaker playback (voice) |
| `numpy` | VAD energy computation + spectrum visualisation (voice) |
| `aiortc` | WebRTC peer connections + Opus codec (voice) |
| `av` | PyAV — audio frame decode/encode used by aiortc (voice) |
| `bcrypt` | Password hashing for server auth (server only, optional) |

Install everything: `pip install textual websockets certifi sounddevice numpy aiortc av bcrypt`
