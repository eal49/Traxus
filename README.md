# Traxus

**Real-time text and voice chat — entirely in your terminal.**

No Electron. No browser. No subscription. Just a fast, keyboard-driven TUI that
runs anywhere Python does.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Traxus                                          alice @ #general    │
├──────────────┬──────────────────────────────────────────────────────┤
│ TEXT          │ [10:42] alice   hey, anyone around?                  │
│  # general   │ [10:42] bob     yep — just finished the build        │
│  # random    │ [10:43] carol   ● audio is crisp, NS is working      │
│  # dev       │ [10:43] alice   nice. joining #dev-voice now         │
│              │                                                       │
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
| Voice + noise suppression | ✓ | ✓ |
| Free forever | ✓ | Paywalled features |
| Open source | ✓ | ✗ |

---

## Features

### Text chat
- Multiple channels — join, leave, create on the fly
- Scrolling message history with Rich-formatted output
- Per-channel member list (`/who`) with live presence updates
- Change your nick at any time (`/nick`)

### Voice
- **Three PTT modes** via `/settings`:
  - `Toggle` — press F9 once to start, again to stop
  - `Hold` — hold F9 while speaking (hands-free release)
  - `VAD` — voice activity detection; mic opens automatically when you speak
- **Spectral noise suppression** — Boll 1979 spectral subtraction filters fan
  noise, AC hum, and background chatter from your mic before it reaches peers.
  Runs capture-side with zero wire-format changes; no extra install needed.
- **ADPCM compression** — 4:1 bandwidth reduction over raw PCM with < 5 % RMS
  error, implemented in pure numpy
- Live mic indicator in the status bar (`● MIC`)
- VAD calibration screen with live energy bar chart and adjustable threshold
- Rebind PTT to any key or mouse button (middle-click recommended)

### Terminal-native UX
- Keyboard-first — full slash command set, no mouse required
- Sidebar groups text and voice channels with live member counts
- Status bar: connection state, username, latency, PTT indicator
- Login (server URL + username) persists across restarts
- Graceful degradation — all text features work without `sounddevice`

### Self-hostable in minutes
- Single asyncio WebSocket server, zero database, zero config files
- Deploy on any Ubuntu 24.04 VPS (Hetzner, OVH, Linode, …)
- TLS via Caddy + Let's Encrypt, subdomain via Duck DNS
- Managed by systemd — see [docs/architecture.md](docs/architecture.md)

---

## Quick Start

```bash
# Install dependencies
pip install textual websockets

# Voice (optional — enables PTT and VAD)
pip install sounddevice numpy

# Terminal 1 — start the server
python -m server.main

# Terminal 2, 3, … — connect clients
python -m client.main
```

On the login screen enter `ws://localhost:8765`, pick a username, press **Connect**.

> **Python 3.14** is the target interpreter. Python 3.12+ should also work.

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
| `/settings` | Open settings (PTT mode, PTT key, VAD sensitivity) |
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
Spectral NS          ← Boll 1979 spectral subtraction
    │  removes stationary noise before peers hear it
    ▼
ADPCM encode         ← 4:1 compression, pure numpy
    │
    ▼  WebSocket binary frame
Server relay
    │
    ▼  WebSocket binary frame
ADPCM decode + play  ← background thread, never blocks TUI
```

No round-trip through the server for noise processing — the filter runs
entirely on your machine, on your mic signal, before it leaves.

---

## Documentation

| Document | Description |
|---|---|
| [docs/commands.md](docs/commands.md) | Every slash command — syntax, arguments, server effects, error conditions |
| [docs/protocol.md](docs/protocol.md) | Full WebSocket protocol — every C2S and S2C message type with field tables |
| [docs/server-rules.md](docs/server-rules.md) | Server business rules — auth, validation, broadcast scope, state invariants |
| [docs/architecture.md](docs/architecture.md) | Architecture deep-dive — audio pipeline, thread model, design decisions |

---

## Project Structure

```
traxus/
├── shared/                  # Zero-dependency protocol + codec layer
│   ├── message_types.py     # C2S / S2C / ErrorCode string constants + VERSION
│   ├── voice_protocol.py    # Binary audio frame pack / unpack
│   └── adpcm.py             # IMA ADPCM codec (encode / decode)
├── server/                  # asyncio WebSocket server
│   ├── main.py              # Entry point, per-connection handler
│   ├── connection_manager.py
│   ├── channel_registry.py
│   └── message_router.py    # Dispatches every C2S message type
├── client/                  # Textual TUI client
│   ├── app.py               # Root App, reactive state, PTT bindings
│   ├── ws_worker.py         # WebSocket recv / send / ping loops
│   ├── audio_engine.py      # Noise suppression + ADPCM + PTT + VAD + playback
│   ├── commands.py          # Slash command parser
│   ├── settings.py          # ~/.config/traxus/settings.json persistence
│   ├── screens/             # LoginScreen, ChatScreen, SettingsScreen,
│   │                        # VadCalibrationScreen, PttKeyScreen
│   └── widgets/             # ChannelSidebar, MessageView, InputBar, StatusBar
├── tests/                   # unittest suite (319 tests)
├── docs/                    # Reference documentation
└── openspec/                # Feature specs and design artefacts
```

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

319 tests covering every server component, the full command parser, the binary
audio protocol, ADPCM round-trips, spectral noise suppression, and an
end-to-end integration test with a real server subprocess and Textual pilot.

---

## Requirements

| Dependency | Required for |
|---|---|
| Python 3.12+ | Everything |
| `textual` | TUI client |
| `websockets` | Client + server |
| `numpy` | ADPCM codec + noise suppression (voice) |
| `sounddevice` | Microphone capture + speaker playback (voice) |

Install everything: `pip install textual websockets sounddevice numpy`
