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
│  # random    │ [10:43] carol   ● audio is crisp, PTT works great    │
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
| Runs in a terminal | **Yes** | No |
| Self-hosted | **Yes** | No |
| Zero telemetry | **Yes** | No |
| Works over SSH | **Yes** | No |
| Voice (PTT) | **Yes** | Yes |
| Free forever | **Yes** | Paywalled features |
| Open source | **Yes** | No |

---

## Features

**Text chat**
- Multiple channels — join, leave, create on the fly
- Scrolling message history with Rich-formatted output
- Per-channel member list (`/who`)
- Change your nick at any time (`/nick`)

**Voice (Push-to-Talk)**
- Low-latency PCM audio relay over WebSocket
- Toggle PTT with `F9` (rebindable to any key or mouse button via `/settings`)
- Works alongside text chat on the same connection
- Live mic indicator in the status bar (`● MIC`)

**Terminal-native UX**
- Keyboard-first — full slash command set, no mouse required
- Sidebar groups text and voice channels separately with live member counts
- Status bar: connection state, username, latency, PTT indicator
- Login persists across restarts

**Self-hostable in minutes**
- Single asyncio WebSocket server, no database required
- Deploy on any Ubuntu 24.04 VPS (OVH, Hetzner, Linode, etc.)
- TLS via Caddy + Let's Encrypt, subdomain via Duck DNS
- systemd service file included — see [deploy/deploy.md](deploy/deploy.md)

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Terminal 1 — start the server
python -m server.main

# Terminal 2, 3, … — start clients
python -m client.main
```

On the login screen enter `ws://localhost:8765`, pick a username, and press **Connect**.

**Voice** requires `sounddevice` and `numpy`:

```bash
pip install sounddevice numpy
```

---

## Slash Commands

| Command | What it does |
|---|---|
| `/join <channel>` | Switch to a text channel |
| `/leave [channel]` | Leave a channel |
| `/create <name>` | Create a new text channel |
| `/vcreate <name>` | Create a new voice channel |
| `/vjoin <channel>` | Join a voice channel |
| `/vleave` | Leave the current voice channel |
| `/nick <name>` | Change your display name |
| `/channels` | List all channels |
| `/who` | List members in the current channel |
| `/settings` | Open settings (rebind PTT key, etc.) |
| `/help` | Print command reference inline |
| `/quit` | Disconnect and exit |

---

## Documentation

| Document | Description |
|---|---|
| [docs/commands.md](docs/commands.md) | Every slash command — syntax, arguments, server effects, error conditions |
| [docs/protocol.md](docs/protocol.md) | Full WebSocket protocol — every C2S and S2C message type with field tables |
| [docs/server-rules.md](docs/server-rules.md) | Server business rules — auth, validation, broadcast scope, state invariants |
| [deploy/deploy.md](deploy/deploy.md) | VPS deployment guide — Ubuntu 24.04 + Duck DNS + Caddy + systemd |

---

## Project Structure

```
traxus/
├── shared/               # Protocol constants and binary audio framing
│   ├── message_types.py  # C2S / S2C / ErrorCode string constants
│   └── voice_protocol.py # PCM frame pack / unpack
├── server/               # asyncio WebSocket server
│   ├── main.py
│   ├── connection_manager.py
│   ├── channel_registry.py
│   └── message_router.py
├── client/               # Textual TUI client
│   ├── app.py
│   ├── ws_worker.py
│   ├── audio_engine.py
│   ├── commands.py
│   ├── screens/          # LoginScreen, ChatScreen, SettingsScreen
│   └── widgets/          # ChannelSidebar, MessageView, InputBar, StatusBar
├── tests/                # unittest suite (167 tests)
├── docs/                 # User-facing reference documentation
└── deploy/               # VPS deployment files (Caddyfile, systemd service)
```

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

All 167 tests must pass. The suite covers unit tests for every server component,
the full command parser, the binary audio protocol, and an end-to-end integration
test with a real server subprocess and Textual pilot.

---

## Requirements

- Python 3.12+
- `textual`, `websockets` (see `requirements.txt`)
- Voice only: `sounddevice`, `numpy`
