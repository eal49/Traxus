# Traxus — Architecture & Design Documentation

> **Version:** 0.2.0
> **Last updated:** 2026-03-13

Traxus is a terminal-based chat application with real-time voice (push-to-talk)
built on Python asyncio WebSockets and the Textual TUI framework. Think of it
as a minimal Discord/TeamSpeak that runs entirely in a terminal.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Package Structure](#2-package-structure)
3. [Server Architecture](#3-server-architecture)
4. [Client Architecture](#4-client-architecture)
5. [WebSocket Protocol](#5-websocket-protocol)
6. [Voice & Audio Subsystem](#6-voice--audio-subsystem)
7. [VPS Networking & Deployment](#7-vps-networking--deployment)
8. [Security Model](#8-security-model)
9. [Design Decisions & Trade-offs](#9-design-decisions--trade-offs)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNET                                     │
│                                                                     │
│   ┌──────────┐    wss://443    ┌──────────────────────────────────┐ │
│   │ Client A ├────────────────►│             VPS                  │ │
│   │ (Textual │◄────────────────│                                  │ │
│   │  TUI)    │                 │  ┌───────────┐   ┌────────────┐ │ │
│   └──────────┘                 │  │   Caddy    │   │  Traxus    │ │ │
│                                │  │  (reverse  ├──►│  Server    │ │ │
│   ┌──────────┐    wss://443    │  │   proxy)   │   │  :8765     │ │ │
│   │ Client B ├────────────────►│  │  :80/:443  │   │ (loopback) │ │ │
│   │ (Textual │◄────────────────│  └───────────┘   └────────────┘ │ │
│   │  TUI)    │                 │                                  │ │
│   └──────────┘                 └──────────────────────────────────┘ │
│                                                                     │
│   ┌──────────┐    ws://8765                                         │
│   │ Client C ├──────────────── (direct, local dev only)             │
│   └──────────┘                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Key properties:**

- **Single server process** — all state is in-memory (no database).
- **WebSocket-only transport** — text frames carry JSON, binary frames carry audio.
- **TLS termination at Caddy** — the Python server never handles certificates.
- **Stateless message routing** — each WebSocket message is self-contained; the server does not maintain request/response correlation.

---

## 2. Package Structure

```
traxus/
├── shared/                    ← Pure logic, no I/O, no framework deps
│   ├── message_types.py       ← C2S, S2C, AuthError, ErrorCode constants + VERSION
│   ├── voice_protocol.py      ← Binary frame pack/unpack for audio
│   └── adpcm.py               ← IMA ADPCM codec (encode/decode)
│
├── server/                    ← asyncio WebSocket server
│   ├── main.py                ← Entry point, asyncio.serve(), connection loop
│   ├── connection_manager.py  ← Client registry, broadcast helpers
│   ├── channel_registry.py    ← Channel CRUD, message history (deque, 50 msgs)
│   └── message_router.py      ← JSON dispatch table, voice relay
│
├── client/                    ← Textual TUI + WebSocket client
│   ├── main.py                ← Entry point (python -m client.main)
│   ├── app.py                 ← TraxusApp root; reactive state, message routing
│   ├── app.tcss               ← Dark Discord-like theme (Textual CSS)
│   ├── ws_worker.py           ← WebSocket recv/send/ping loops
│   ├── audio_engine.py        ← Mic capture + speaker playback + VAD
│   ├── commands.py            ← Slash command parser (ParsedCommand)
│   ├── settings.py            ← ~/.config/traxus/settings.json persistence
│   ├── screens/
│   │   ├── login_screen.py    ← Server URL + username form
│   │   ├── chat_screen.py     ← 3-panel layout (sidebar, messages, members)
│   │   ├── settings_screen.py ← PTT key/mode/VAD config modal
│   │   └── vad_calibration_screen.py ← Live energy bar chart for VAD tuning
│   └── widgets/
│       ├── channel_sidebar.py ← Text/voice channel list (ListView)
│       ├── message_view.py    ← Scrolling RichLog with nick coloring
│       ├── input_bar.py       ← Message input with channel label
│       ├── status_bar.py      ← Connection dot, latency, PTT indicator
│       └── member_panel.py    ← Channel members + voice participants
│
├── tests/                     ← unittest suite
├── deploy/                    ← VPS deployment configs
│   ├── deploy.md              ← Step-by-step deployment guide
│   ├── Caddyfile              ← Caddy reverse proxy config
│   ├── traxus-server.service  ← systemd unit file
│   └── requirements-server.txt← Server-only pip dependencies
│
└── docs/                      ← Documentation
```

### Dependency graph

```
shared/message_types.py ◄──── server/message_router.py
shared/voice_protocol.py ◄─── server/message_router.py
shared/adpcm.py ◄──────────── client/audio_engine.py
                  ◄──────────── shared/voice_protocol.py (codec tags)

shared/ has ZERO runtime dependencies (stdlib only).
server/ depends on: websockets, numpy, shared/
client/ depends on: textual, websockets, sounddevice (optional), numpy (optional), shared/
```

---

## 3. Server Architecture

### 3.1. Core Singletons

The server creates exactly three objects at startup and passes them by reference
to every connection handler:

```
main.py
  ├─ ConnectionManager()   ← tracks all live clients
  ├─ ChannelRegistry()     ← channels, topics, history
  └─ MessageRouter(cm, cr) ← dispatches messages to handlers
```

### 3.2. Connection Lifecycle

```
┌──────────────┐
│ TCP connect   │
│ WS handshake  │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────────────────────────┐
│ client=None  │     │ Only C2S.AUTH is accepted.        │
│ (unauthed)   │────►│ All other types → NOT_AUTHENTICATED│
└──────┬───────┘     └──────────────────────────────────┘
       │ AUTH ok
       ▼
┌──────────────┐
│ client=       │     ┌──────────────────────────────────┐
│ ConnectedClient│───►│ Full dispatch table available.    │
│ (authed)      │     │ Auto-joined to #general.         │
└──────┬───────┘     └──────────────────────────────────┘
       │ WS close / error
       ▼
┌──────────────┐
│ on_disconnect │ ← broadcast leave/voice_state to all peers
│ unregister()  │ ← remove from ConnectionManager
└──────────────┘
```

### 3.3. ConnectedClient Data Model

```python
@dataclass
class ConnectedClient:
    ws: ServerConnection          # WebSocket handle
    user_id: str                  # UUID4 (assigned at auth)
    username: str                 # Unique, 1-32 chars, no spaces
    channels: set[str]            # Text channels currently joined
    voice_channels: set[str]      # Voice channels currently joined
    connected_at: float           # time.time() at auth
```

**Registries in ConnectionManager:**

| Registry | Type | Key | Purpose |
|----------|------|-----|---------|
| `_clients` | `dict[str, ConnectedClient]` | `user_id` | Primary lookup |
| `_nick_to_id` | `dict[str, str]` | `username` | Uniqueness check, nick→id resolve |

### 3.4. Channel Data Model

```python
@dataclass
class Channel:
    name: str                     # Lowercase, 1-32 chars, [a-z0-9_-]
    topic: str                    # Description
    created_by: str               # Username of creator
    type: str = "text"            # "text" or "voice"
    created_at: float             # time.time()
    history: deque(maxlen=50)     # Last 50 messages (text channels only)
```

**Default channels** (bootstrapped at startup):

| Name | Topic | Type |
|------|-------|------|
| `general` | General chat | text |
| `random` | Anything goes | text |
| `dev` | Dev discussion | text |

### 3.5. Message Router Dispatch Table

```
┌──────────────────┬──────────────────────┬──────────────────────────┐
│ C2S Type         │ Handler              │ Side Effects             │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ auth             │ _handle_auth         │ Register client, auto-   │
│                  │                      │ join #general, send      │
│                  │                      │ channel_list             │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ join             │ _handle_join         │ Add to channel, send     │
│                  │                      │ history, broadcast       │
│                  │                      │ user_list + system msg   │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ leave            │ _handle_leave        │ Remove from channel,     │
│                  │                      │ broadcast user_list      │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ message          │ _handle_message      │ Auto-join if not member, │
│                  │                      │ add to history,          │
│                  │                      │ broadcast chat           │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ nick             │ _handle_nick         │ Update ConnectionManager,│
│                  │                      │ broadcast nick_changed   │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ create           │ _handle_create       │ Create channel, broadcast│
│                  │                      │ channel_created +        │
│                  │                      │ channel_list             │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ list_channels    │ _handle_list_channels│ Send channel_list        │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ ping             │ _handle_ping         │ Echo timestamp as pong   │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ voice_join       │ _handle_voice_join   │ Add to voice_channels,   │
│                  │                      │ broadcast voice_state    │
├──────────────────┼──────────────────────┼──────────────────────────┤
│ voice_leave      │ _handle_voice_leave  │ Remove from voice,       │
│                  │                      │ broadcast voice_state    │
└──────────────────┴──────────────────────┴──────────────────────────┘
```

### 3.6. Broadcasting

The ConnectionManager pre-serializes JSON once and sends the same bytes to all
recipients. Failed sends to individual clients are silently ignored (the client
will be cleaned up on the next recv failure).

```
broadcast_to_channel(channel, payload, exclude_id=None)
  ├─ raw = json.dumps(payload)
  ├─ for client in clients_in_channel(channel):
  │    if client.user_id != exclude_id:
  │        await client.ws.send(raw)    # fire-and-forget
  └─ (errors swallowed per-client)
```

---

## 4. Client Architecture

### 4.1. Concurrency Model

Textual owns the asyncio event loop. All async work runs on the same loop.

```
┌─────────────────────────────────────────────────────────────┐
│                   ASYNCIO EVENT LOOP                         │
│              (owned by Textual App.run())                    │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Textual Message  │    │  WsWorker (asyncio.Task)     │  │
│  │  Pump (sync       │    │  ├─ _recv_loop  (async for)  │  │
│  │  handlers, UI     │    │  ├─ _send_loop  (queue race) │  │
│  │  rendering)       │    │  └─ _ping_loop  (30s timer)  │  │
│  └──────────────────┘    └──────────────────────────────┘  │
│                                                             │
│  ┌──────────────────┐                                      │
│  │  capture_loop     │ ← drains audio queue, sends frames  │
│  │  (asyncio.Task)   │                                      │
│  └──────────────────┘                                      │
└─────────────────────────────────────────────────────────────┘
         ▲                              ▲
         │ call_soon_threadsafe         │ call_soon_threadsafe
         │                              │
┌────────┴───────┐             ┌────────┴───────┐
│ sounddevice     │             │ Playback daemon │
│ audio thread    │             │ thread          │
│ (mic capture)   │             │ (sd.OutputStream│
│                 │             │  .write)        │
└─────────────────┘             └─────────────────┘
```

**Critical rule:** Textual sync message handlers must never block or await.
They may only do `queue.put_nowait()` and attribute reads/writes (nanosecond
operations). Anything slower freezes the entire TUI.

### 4.2. Startup Sequence

```
python -m client.main
  └─ TraxusApp.run()
       └─ on_mount()
            ├─ Initialize AudioEngine, settings, state
            └─ push_screen(LoginScreen)
                 └─ User fills server URL + username
                      └─ connect_to_server(url, username)
                           └─ WsWorker.run() scheduled as exclusive asyncio Task
                                └─ AUTH sent → auth_ok received
                                     └─ switch_screen(ChatScreen)
                                          └─ Auto-joined to #general
```

### 4.3. Screen & Widget Hierarchy

```
TraxusApp
├─ LoginScreen (initial)
│  ├─ Static (ASCII logo)
│  ├─ Static (subtitle)
│  ├─ Input  (server URL)
│  ├─ Input  (username)
│  ├─ Button (Connect)
│  └─ Label  (error display)
│
├─ ChatScreen (after auth)
│  ├─ Header (show_clock=True)
│  ├─ Horizontal
│  │  ├─ ChannelSidebar (width: 22)
│  │  │  ├─ Static ("CHANNELS" header)
│  │  │  └─ ListView
│  │  │     ├─ ListItem [dim bold]TEXT[/]
│  │  │     ├─ ListItem "# general"     ← highlight if active
│  │  │     ├─ ListItem "# random"
│  │  │     ├─ ListItem "# dev"
│  │  │     ├─ ListItem [dim bold]VOICE[/]
│  │  │     └─ ListItem "♪ voice-room"
│  │  ├─ Vertical (id="main-panel", 1fr)
│  │  │  ├─ MessageView (RichLog, 1fr)
│  │  │  └─ InputBar (height: 3)
│  │  │     ├─ Static "#general ›"
│  │  │     └─ Input (message)
│  │  └─ MemberPanel (width: 20)
│  │     ├─ Members section
│  │     └─ In Voice section
│  └─ StatusBar (dock: bottom, height: 2)
│     └─ "● connected  42ms  alice  🔊 voice-room  🎤 PTT ON"
│
├─ SettingsScreen (modal, pushed over ChatScreen)
│  └─ ListView
│     ├─ PTT Key: F9
│     ├─ PTT Mode: Toggle / Hold / VAD
│     └─ VAD Sensitivity: Low / Medium / High / Very High / Custom
│
├─ PttKeyScreen (modal, key capture)
│
└─ VadCalibrationScreen (modal, live audio energy chart)
   ├─ Static (title)
   ├─ Static (ASCII bar chart, 40x24)
   └─ Static (hint: Up/Down/PgUp/PgDn/Enter/Esc)
```

### 4.4. Reactive State

| Property | Type | Updated by | Watched by |
|----------|------|------------|------------|
| `connection_state` | `str` | WsWorker `ConnectionStateChanged` | StatusBar |
| `current_channel` | `str` | `joined` server message | InputBar label, sidebar highlight |
| `current_voice_channel` | `str` | `voice_state` server message | StatusBar, VAD lifecycle |
| `username` | `str` | `auth_ok`, `nick_changed` | StatusBar |

### 4.5. Client-Side Message Flow

```
           ┌─────────────────────────────────┐
           │         WebSocket Server         │
           └──────────┬──────────────────────┘
                      │
              ┌───────┴────────┐
              │   WsWorker     │
              │  _recv_loop    │
              └───────┬────────┘
                      │
          ┌───────────┼───────────┐
          │ bytes     │ str       │
          ▼           ▼           │
   AudioFrame    ServerMessage    │
   (posted to    (posted to      │
    app pump)     app pump)      │
          │           │           │
          ▼           ▼           │
   AudioEngine   match type:     │
   .play()       ├─ auth_ok      │
   (enqueue to   ├─ channel_list │
    daemon       ├─ joined       │
    thread)      ├─ chat         │
                 ├─ system       │
                 ├─ voice_state  │
                 ├─ user_list    │
                 ├─ nick_changed │
                 ├─ pong         │
                 └─ error        │
                      │           │
                      ▼           │
               ChatScreen        │
               .append_*()       │
               .update_*()       │
                                  │
   ┌──────────────────────────────┘
   │  User input
   ▼
InputBar → app.handle_input(text)
           ├─ plain text → WsWorker.enqueue({type: message, ...})
           └─ /command   → _execute_command(ParsedCommand)
                            └─ WsWorker.enqueue({type: *, ...})
```

### 4.6. Reconnection Strategy

WsWorker implements exponential backoff:

```
Initial delay:  1 second
Maximum delay: 30 seconds
Growth:        delay *= 2
Reset:         delay = 1s on successful connection

Loop:
  try connect → auth → gather(recv, send, ping)
  on failure  → post "reconnecting", sleep(delay), delay *= 2
  on cancel   → break
  finally     → post "disconnected"
```

The UI shows `◌ reconnecting` (yellow) during backoff and `● connected` (green)
once the handshake succeeds again.

### 4.7. Theme & Visual Design

Discord-inspired dark theme defined in `client/app.tcss`:

| Token | Hex | Usage |
|-------|-----|-------|
| `$background` | `#1a1b1e` | Main background |
| `$surface` | `#232428` | Sidebar, member panel |
| `$surface-darken-1` | `#1d1e22` | Status bar |
| `$border-color` | `#3d3f46` | Panel dividers |
| `$primary` | `#5865f2` | Blurple accents |
| `$accent` | `#57f287` | Green highlights |
| `$text` | `#dcddde` | Main text |
| `$text-muted` | `#72767d` | System messages |
| `$error` | `#ed4245` | Error text |

Nick colors use an 8-color palette assigned via MD5 hash of the username:
blurple, green, yellow, pink, red, cyan, magenta, orange.

---

## 5. WebSocket Protocol

### 5.1. Transport

- **Text frames** carry JSON objects with a mandatory `"type"` field.
- **Binary frames** carry audio data with a custom binary header.
- **Protocol version:** `0.2.0` — enforced during auth handshake.

### 5.2. Authentication Handshake

```
Client                              Server
  │                                    │
  │──── {type: "auth",            ────►│
  │      version: "0.2.0",            │
  │      username: "alice"}            │
  │                                    │
  │◄─── {type: "auth_ok",        ─────│  ← success
  │      user_id: "<uuid>",           │
  │      username: "alice",            │
  │      server_version: "0.2.0"}      │
  │                                    │
  │◄─── {type: "channel_list",   ─────│  ← auto-sent after auth
  │      channels: [...]}             │
  │                                    │
  │◄─── {type: "joined",         ─────│  ← auto-join #general
  │      channel: "general",          │
  │      history: [...]}              │
```

**Auth rejection reasons:**

| Reason | Error constant | When |
|--------|---------------|------|
| Version mismatch | `AuthError.VERSION_MISMATCH` | Client version != server version |
| Invalid username | `AuthError.INVALID_USERNAME` | Empty, >32 chars, or contains spaces |
| Username taken | `AuthError.USERNAME_TAKEN` | Another client has the same nick |

On `VERSION_MISMATCH`, the server closes the WebSocket after sending the error.

### 5.3. Client-to-Server (C2S) Messages

```json
// Join a channel
{"type": "join", "channel": "random"}

// Leave a channel
{"type": "leave", "channel": "random"}

// Send a chat message
{"type": "message", "channel": "general", "content": "Hello!"}

// Change nickname
{"type": "nick", "username": "new_name"}

// Create a channel
{"type": "create", "channel": "lounge", "channel_type": "text"}
{"type": "create", "channel": "voice-1", "channel_type": "voice"}

// List channels
{"type": "list_channels"}

// Ping (latency measurement)
{"type": "ping", "ts": 1710300000.123}

// Join voice channel
{"type": "voice_join", "channel": "voice-1"}

// Leave voice channel
{"type": "voice_leave", "channel": "voice-1"}
```

### 5.4. Server-to-Client (S2C) Messages

```json
// Channel list (sent after auth + after create)
{"type": "channel_list", "channels": [
    {"name": "general", "topic": "General chat", "member_count": 3, "type": "text"},
    {"name": "voice-1", "topic": "Voice room", "member_count": 1, "type": "voice"}
]}

// Joined a channel (with history)
{"type": "joined", "channel": "general", "history": [
    {"user_id": "...", "username": "bob", "content": "hi", "ts": 1710300000.0}
]}

// Left a channel
{"type": "left", "channel": "random"}

// Chat message
{"type": "chat", "channel": "general", "user_id": "...",
 "username": "alice", "content": "Hello!", "ts": 1710300000.5}

// System notification
{"type": "system", "channel": "general", "content": "alice joined #general"}

// Nick changed (broadcast to all)
{"type": "nick_changed", "old_nick": "alice", "new_nick": "alice_",
 "user_id": "..."}

// Channel created (broadcast to all)
{"type": "channel_created", "channel": "lounge", "created_by": "alice"}

// User list for a channel
{"type": "user_list", "channel": "general",
 "users": [{"user_id": "...", "username": "alice"}]}

// Voice state update
{"type": "voice_state", "channel": "voice-1",
 "users": [{"user_id": "...", "username": "alice"}]}

// Pong (echo client timestamp)
{"type": "pong", "ts": 1710300000.123}

// Error
{"type": "error", "code": "no_such_channel", "detail": "..."}
```

### 5.5. Error Codes

| Code | Trigger |
|------|---------|
| `not_authenticated` | Non-auth message before handshake |
| `invalid_json` | Malformed JSON text frame |
| `unknown_message_type` | Unrecognized `type` field |
| `no_such_channel` | Channel does not exist |
| `channel_exists` | Duplicate channel name on create |
| `nick_taken` | Username already in use |
| `invalid_channel_name` | Fails regex `^[a-z0-9_-]{1,32}$` |
| `not_a_voice_channel` | voice_join on a text channel |

### 5.6. Keepalive

The client sends `C2S.PING` every **30 seconds** with a timestamp. The server
echoes the timestamp back as `S2C.PONG`. The client computes round-trip latency
and displays it in the status bar (e.g., `42ms`).

---

## 6. Voice & Audio Subsystem

### 6.1. Audio Parameters

| Parameter | Value |
|-----------|-------|
| Sample rate | 16,000 Hz |
| Channels | 1 (mono) |
| Sample format | int16 (signed 16-bit little-endian) |
| Block size | 320 samples (~20 ms per callback) |
| Playback queue | 10 frames max (drop-oldest on overflow) |

### 6.2. Binary Frame Format

Audio is transmitted as WebSocket binary frames with a compact header.

**Client-to-Server (C2S) frame:**

```
Byte   Field
─────────────────────────────────
0      Channel name length (N)
1..N   Channel name (UTF-8)
N+1    Codec tag
N+2..  Audio payload
```

**Server-to-Client (S2C) frame:**

```
Byte       Field
─────────────────────────────────
0          Channel name length (N)
1..N       Channel name (UTF-8)
N+1        Username length (M)
N+2..N+1+M Username (UTF-8)
N+M+2      Codec tag
N+M+3..    Audio payload
```

The server adds the sender's username to the frame so recipients know who is
speaking. This is done in `MessageRouter.relay_voice()`.

### 6.3. Codec Tags

| Tag | Name | Description |
|-----|------|-------------|
| `0x00` | `CODEC_RAW` | Raw int16 little-endian PCM (fallback) |
| `0x01` | `CODEC_ADPCM` | IMA ADPCM 4:1 compression |

### 6.4. IMA ADPCM Codec

The custom ADPCM implementation in `shared/adpcm.py` provides ~4:1 compression
over raw PCM with minimal quality loss (RMS error < 5%).

**ADPCM payload layout:**

```
Byte    Field
──────────────────────────────────────
0-1     Predictor (int16 LE) — initial sample value
2-3     Step index (int16 LE) — initial quantizer state
4..     Nibble-packed samples (2 samples per byte, low nibble first)
```

**Encoding** happens in the sounddevice audio thread callback (off the Textual
pump). **Decoding** happens in the playback daemon thread (also off the pump).
This ensures the TUI never blocks on codec operations.

### 6.5. PTT (Push-to-Talk) State Machine

```
                    ┌─────────────────┐
                    │    IDLE          │
                    │  (not in voice)  │
                    └────────┬────────┘
                             │ /vjoin
                             ▼
                    ┌─────────────────┐
         ┌────────►│  IN VOICE        │◄────────┐
         │         │  (mic off)       │         │
         │         └────────┬────────┘         │
         │                  │                   │
    ┌────┴────┐    F9 press │          F9 press │
    │ toggle  │    ─────────┤          ─────────┤
    │ mode    │             │                   │
    │ F9 off  │    ┌────────▼────────┐         │
    └─────────┘    │  TRANSMITTING    │─────────┘
                   │  (mic on, sending│
                   │   audio frames)  │
                   └──────────────────┘

    PTT Modes:
    ├─ toggle: F9 toggles on/off
    ├─ hold:   F9 down = on, F9 up = off (with debounce)
    └─ vad:    auto-transmit on voice activity detection
```

### 6.6. VAD (Voice Activity Detection)

When PTT mode is set to "vad", the microphone stays open continuously and
monitors audio energy (RMS). When energy exceeds the threshold, transmission
starts automatically; when it drops below, a hangover timer stops transmission.

**Sensitivity presets:**

| Preset | RMS Threshold | Behavior |
|--------|--------------|----------|
| Low | 600 | Only loud speech triggers |
| Medium | 400 | Normal conversation |
| High | 250 | Quieter speech triggers |
| Very High | 100 | Very sensitive |
| Custom | User-defined | Set via calibration screen |

The calibration screen shows a live 40x24 ASCII bar chart of microphone energy
with a movable threshold line (Up/Down = fine ±10, PgUp/PgDn = coarse ±100).

### 6.7. Audio Thread Safety

```
┌────────────────────────────┐
│ sounddevice audio thread   │  ← Called every ~20ms by OS audio subsystem
│ _input_callback(indata)    │
│   ├─ compute RMS           │
│   ├─ ADPCM encode          │  ← Codec work done HERE, not on pump
│   └─ call_soon_threadsafe  │  ← Bridge to asyncio loop
│        └─ queue.put_nowait │  ← Nanosecond operation
└────────────────────────────┘
              │
              ▼
┌────────────────────────────┐
│ asyncio loop               │
│ capture_loop coroutine     │
│   └─ await queue.get()     │
│        └─ ws.send(frame)   │  ← Send to server
└────────────────────────────┘

┌────────────────────────────┐
│ Textual pump (sync)        │
│ on_audio_frame(data)       │
│   └─ AudioEngine.play()    │
│        └─ play_queue       │  ← put_nowait (~4 µs), returns instantly
│           .put_nowait()    │
└────────────────────────────┘
              │
              ▼
┌────────────────────────────┐
│ Playback daemon thread     │  ← Blocking I/O is fine here
│ _playback_worker           │
│   ├─ play_queue.get()      │  ← threading.Queue, blocks until data
│   ├─ ADPCM decode          │  ← Codec work done HERE
│   └─ sd.OutputStream      │
│      .write(pcm)           │  ← Blocking write to speaker
└────────────────────────────┘
```

**Key invariant:** `AudioEngine.play()` must complete in microseconds. It only
calls `queue.put_nowait()`. All decoding and device I/O happens in the daemon
thread. If `play()` ever blocked, it would freeze the entire TUI for all users.

---

## 7. VPS Networking & Deployment

### 7.1. Network Topology

```
┌──────────────────────────────────────────────────────────────────────┐
│                          INTERNET                                    │
│                                                                      │
│   ┌─────────┐         DNS query                                     │
│   │ Client  ├──────────────────────►  Duck DNS                      │
│   │         │◄──────────────────────  traxus.duckdns.org → VPS IP   │
│   └────┬────┘                                                        │
│        │                                                             │
│        │  TCP :443 (TLS/WSS)                                        │
│        │                                                             │
│   ┌────▼─────────────────────────────────────────────────────────┐   │
│   │                   VPS (Ubuntu 24.04, x86-64)                  │   │
│   │                   1 vCore, 1+ GB RAM                         │   │
│   │                                                              │   │
│   │   ┌──────────────────────────────────────────────────────┐   │   │
│   │   │           Provider Firewall / Security Group          │   │   │
│   │   │   ┌────────┬──────────┬──────────────────────────┐   │   │   │
│   │   │   │ Port   │ Protocol │ Purpose                  │   │   │   │
│   │   │   ├────────┼──────────┼──────────────────────────┤   │   │   │
│   │   │   │ 22     │ TCP      │ SSH administration       │   │   │   │
│   │   │   │ 80     │ TCP      │ ACME (Let's Encrypt)     │   │   │   │
│   │   │   │ 443    │ TCP      │ HTTPS / WSS traffic      │   │   │   │
│   │   │   │ 8765   │ TCP      │ BLOCKED (loopback only)  │   │   │   │
│   │   │   └────────┴──────────┴──────────────────────────┘   │   │   │
│   │   └──────────────────────────────────────────────────────┘   │   │
│   │                                                              │   │
│   │   ┌──────────────────────────────────────────────────────┐   │   │
│   │   │                  UFW Firewall                        │   │   │
│   │   │   ALLOW 22/tcp, 80/tcp, 443/tcp                      │   │   │
│   │   │   DENY  8765/tcp                                     │   │   │
│   │   └──────────────────────────────────────────────────────┘   │   │
│   │                                                              │   │
│   │   ┌───────────────────────┐    ┌──────────────────────────┐  │   │
│   │   │       Caddy           │    │    Traxus Server         │  │   │
│   │   │                       │    │                          │  │   │
│   │   │  :443 (HTTPS/WSS)     │    │  127.0.0.1:8765 (WS)    │  │   │
│   │   │  :80  (ACME redirect) │    │  (loopback only)        │  │   │
│   │   │                       │    │                          │  │   │
│   │   │  TLS termination      │    │  Plain WebSocket         │  │   │
│   │   │  Let's Encrypt auto   │    │  JSON text frames        │  │   │
│   │   │  HTTP/2 support       │    │  Binary audio frames     │  │   │
│   │   │  reverse_proxy ───────┼───►│                          │  │   │
│   │   │   localhost:8765      │    │  Managed by systemd      │  │   │
│   │   └───────────────────────┘    └──────────────────────────┘  │   │
│   │                                                              │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2. Request Flow (Client Connection)

```
 Client                Duck DNS         Caddy (:443)        Traxus (:8765)
   │                      │                 │                     │
   │─ DNS lookup ────────►│                 │                     │
   │◄─ VPS IP ────────────│                 │                     │
   │                      │                 │                     │
   │─ TCP SYN ──────────────────────────────►                     │
   │◄─ TCP SYN-ACK ─────────────────────────│                     │
   │─ TLS ClientHello ─────────────────────►│                     │
   │◄─ TLS ServerHello + Cert ──────────────│                     │
   │─ TLS Finished ────────────────────────►│                     │
   │                      │                 │                     │
   │─ HTTP Upgrade: websocket ─────────────►│                     │
   │                      │                 │─ WS connect ───────►│
   │                      │                 │◄─ WS accept ────────│
   │◄─ 101 Switching Protocols ─────────────│                     │
   │                      │                 │                     │
   │═══════════════ WSS tunnel (encrypted) ═══════════════════════│
   │                      │                 │                     │
   │─ {type:"auth",...} ────────────────────┼────────────────────►│
   │◄─ {type:"auth_ok",...} ────────────────┼─────────────────────│
   │◄─ {type:"channel_list",...} ───────────┼─────────────────────│
   │◄─ {type:"joined",...} ─────────────────┼─────────────────────│
   │                      │                 │                     │
   │  (bidirectional text + binary frames)  │                     │
```

### 7.3. TLS Certificate Management

Caddy handles TLS automatically:

1. On first startup, Caddy requests a certificate from Let's Encrypt.
2. Let's Encrypt issues an HTTP-01 challenge on port 80.
3. Caddy solves the challenge and receives a certificate for `traxus.duckdns.org`.
4. Caddy auto-renews the certificate before expiry (every ~60 days).
5. No manual certificate management is ever required.

**Caddyfile:**

```
traxus.duckdns.org {
    reverse_proxy localhost:8765
}
```

This single-line config gives you: TLS 1.3, HTTP/2, automatic HTTPS redirect,
and WebSocket proxying.

### 7.4. systemd Service

```ini
[Unit]
Description=Traxus WebSocket Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Traxus
ExecStart=/home/ubuntu/Traxus/.venv/bin/python -m server.main
Environment=TRAXUS_HOST=127.0.0.1
Environment=TRAXUS_PORT=8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Key details:**

- **`TRAXUS_HOST=127.0.0.1`** — binds to loopback only. Direct internet
  access to port 8765 is impossible even if the firewall misconfigures.
- **`Restart=on-failure`** — systemd restarts the server after 5 seconds if
  it crashes.
- **No root required** — runs as the `ubuntu` user.

### 7.5. Server Dependencies

```
# deploy/requirements-server.txt
websockets>=14.0
numpy>=1.26
```

The server does not need `textual`, `sounddevice`, or any client dependencies.
`numpy` is required for the ADPCM codec used in voice relay.

### 7.6. Infrastructure Summary

| Component | Role | Details |
|-----------|------|---------|
| VPS (any provider) | VPS | Ubuntu 24.04, x86-64, 1+ vCore / 1+ GB RAM |
| Ubuntu 24.04 | OS | Python 3.12, systemd |
| Duck DNS | Dynamic DNS | Free subdomain → VPS public IP |
| Caddy | Reverse proxy | TLS termination, auto Let's Encrypt, WSS→WS |
| UFW | Firewall | Allow 22, 80, 443; deny 8765 |
| systemd | Process manager | Auto-start, restart on failure |
| Python venv | Isolation | Server dependencies only |

---

## 8. Security Model

### 8.1. Authentication

- **No passwords** — authentication is username-only (lobby-style).
- Username must be 1-32 characters, no spaces.
- Duplicate usernames are rejected (`USERNAME_TAKEN`).
- Each client gets a UUID4 `user_id` on successful auth.

### 8.2. Network Security

- **TLS at the edge** — Caddy terminates TLS; all client traffic is encrypted.
- **Loopback binding** — the Python server only listens on `127.0.0.1:8765`,
  unreachable from the internet.
- **No port exposure** — port 8765 is explicitly denied in UFW.
- **Version handshake** — clients must match the server's protocol version
  (`0.2.0`) or the connection is rejected and closed.

### 8.3. Input Validation

| Input | Validation |
|-------|-----------|
| Username | 1-32 chars, no spaces |
| Channel name | Regex `^[a-z0-9_-]{1,32}$` |
| Message content | Non-empty string (Rich markup escaped on display) |
| JSON frames | Parsed in try/except; malformed → `INVALID_JSON` error |
| Binary frames | Parsed with length-prefixed fields; malformed → silently dropped |
| Protocol version | Exact match required |

### 8.4. Limitations

- No end-to-end encryption (server sees all messages and audio).
- No persistent accounts or password authentication.
- No rate limiting (a malicious client could flood the server).
- No message persistence beyond the 50-message in-memory history per channel.
- Server restart clears all state.

---

## 9. Design Decisions & Trade-offs

### 9.1. Single-Process, In-Memory Server

**Decision:** All server state lives in Python dicts and deques. No database.

**Why:** Traxus targets small groups (friends, teams). A database would add
deployment complexity, operational overhead, and latency for zero benefit at
this scale. The 50-message history cap keeps memory bounded.

**Trade-off:** Server restart loses all state. No message persistence, no
offline message delivery, no audit trail. Acceptable for the target use case.

### 9.2. Textual Owns the Event Loop

**Decision:** The Textual TUI framework owns the asyncio event loop. The
WebSocket worker runs as an `asyncio.Task` on the same loop.

**Why:** Textual requires loop ownership for its rendering pipeline. Running
WebSocket I/O on the same loop avoids cross-thread synchronization for UI
updates. `app.post_message()` is the bridge — it safely enqueues events from
coroutines to the Textual message pump.

**Trade-off:** The WebSocket worker cannot use `asyncio.run()` — it must
cooperate with Textual's loop. Long-running sync operations would freeze both
networking and the UI.

### 9.3. Separate Audio Threads

**Decision:** Audio capture (sounddevice callback) and playback
(`_playback_worker`) each run in their own threads, separate from the asyncio
loop and the Textual pump.

**Why:** Audio I/O is inherently real-time and blocking. `sd.OutputStream.write()`
blocks until the OS audio buffer has room. If this happened on the Textual pump,
the entire TUI would freeze during audio playback. The bridge is
`loop.call_soon_threadsafe(queue.put_nowait, data)` — a nanosecond operation
that transfers data without blocking either side.

**Trade-off:** Three concurrency domains (asyncio, Textual pump, audio threads)
increase complexity. The `call_soon_threadsafe` bridge must be used correctly —
no direct attribute access across thread boundaries.

### 9.4. ADPCM Over Raw PCM

**Decision:** Audio is compressed with IMA ADPCM (~4:1 ratio) before
transmission. Raw PCM is kept as a fallback.

**Why:** At 16 kHz mono int16, raw PCM produces 32 KB/s per speaker. ADPCM
reduces this to ~8 KB/s with minimal quality loss (RMS error < 5%). This
matters on bandwidth-constrained connections and reduces server relay load.

**Trade-off:** Custom codec implementation (120 lines) instead of using Opus
or another standard codec. ADPCM quality is lower than Opus, but has zero
external dependencies beyond numpy.

### 9.5. Caddy for TLS Termination

**Decision:** Use Caddy as a reverse proxy instead of adding TLS to the Python
server.

**Why:** Caddy provides automatic Let's Encrypt certificate management with
zero configuration beyond a 3-line Caddyfile. The Python `websockets` library
supports TLS but requires manual certificate management, renewal scripts, and
certbot. Caddy eliminates all of that.

**Trade-off:** Additional process to manage. However, Caddy is a single static
binary with systemd integration, so operational overhead is minimal.

### 9.6. Duck DNS for Domain Names

**Decision:** Use Duck DNS (free dynamic DNS) instead of purchasing a domain.

**Why:** Zero cost, instant setup, sufficient for personal/small-team use.
The subdomain `traxus.duckdns.org` is all that's needed for Let's Encrypt
to issue a certificate.

**Trade-off:** Dependency on a free third-party service. Duck DNS could go
down or discontinue service. For production use, a purchased domain would be
more reliable.

### 9.7. No Database, No ORM

**Decision:** Channels and messages are stored in Python dataclasses and
`collections.deque`.

**Why:** The server is designed to be ephemeral. Channel history is capped at
50 messages. There are no user accounts to persist. Adding SQLite or PostgreSQL
would increase deployment complexity without solving a real problem at the
target scale.

**Trade-off:** No search, no message history beyond 50, no persistence across
restarts. If Traxus needed to scale to hundreds of users, a database would
become necessary.

### 9.8. Username-Only Authentication

**Decision:** No passwords, no tokens, no OAuth. Users just pick a username.

**Why:** Traxus is designed for trusted groups (friends, team members on a
private VPS). Password management adds friction and security responsibility
(hashing, storage, reset flows) without benefit when the server is already
access-controlled at the network level.

**Trade-off:** Anyone who can reach the server can connect as any unclaimed
username. No identity verification, no impersonation protection beyond "first
come, first served."

### 9.9. Pre-Serialized Broadcasts

**Decision:** `broadcast_to_channel()` calls `json.dumps()` once and sends
the same bytes to all recipients.

**Why:** Avoids re-serializing the same payload N times for N recipients.
For a chat message broadcast to 20 users, this saves 19 JSON serialization
calls.

**Trade-off:** Cannot customize the payload per-recipient (e.g., cannot
exclude the sender's own message server-side). Instead, the client filters
its own messages by checking `user_id`.

### 9.10. Graceful Audio Degradation

**Decision:** `sounddevice` and `numpy` are optional imports. Voice features
degrade gracefully when they're unavailable.

**Why:** Not all platforms or environments have audio hardware or the required
native libraries. The chat functionality should work everywhere — voice is an
enhancement, not a requirement.

**Trade-off:** Voice features show "not available" messages instead of
crashing, but users on systems without audio support cannot participate in
voice channels at all.
