# Traxus — Developer Guide for Claude

## Testing requirement

**Run the full test suite after every edit, no exceptions.**

```bash
python -m unittest discover -s tests -v
```

All tests must pass before considering any change complete. If a test breaks,
fix it before moving on. Never skip, comment out, or weaken a test to make it
pass — fix the underlying code instead.

---

## Architecture overview

Traxus is a terminal chat application with optional voice (PTT). It is split
into three packages that share one asyncio event loop on the client side.

```
shared/          ← constants and binary framing (no I/O, no framework deps)
server/          ← asyncio WebSocket server
client/          ← Textual TUI + WebSocket client
tests/           ← pytest suite (unit + integration)
docs/            ← user-facing documentation
openspec/        ← feature specs and design artefacts
```

### shared/

| File | Purpose |
|---|---|
| `message_types.py` | `C2S`, `S2C`, `AuthError`, `ErrorCode` string constants + `VERSION` |
| `voice_protocol.py` | Binary frame packing/unpacking for PCM audio (`pack_c2s`, `unpack_s2c`) |

These modules have zero runtime dependencies beyond the stdlib. Both server and
client import them. **Never add I/O or framework imports here.**

---

### server/

Stateless request/response over WebSocket. Each client connection runs in one
asyncio coroutine; all state is held in shared objects passed by reference.

| File | Class | Responsibility |
|---|---|---|
| `main.py` | — | `asyncio.serve()` entry point; creates the three singletons below |
| `connection_manager.py` | `ConnectionManager` | Registry of live `ConnectedClient` objects; broadcast helpers |
| `channel_registry.py` | `ChannelRegistry` | Channel metadata, membership, message history |
| `message_router.py` | `MessageRouter` | Decodes raw WebSocket messages and dispatches to typed handlers |

**Message flow (server side)**

```
websocket frame
  └─ server/main.py per-connection coroutine
       ├─ text frame  → MessageRouter.dispatch(raw, ws, client)
       │                  └─ _handle_<type>(payload, ws, client)
       │                       └─ ConnectionManager / ChannelRegistry mutations
       │                            └─ ws.send(json) / broadcast_to_channel(...)
       └─ binary frame → MessageRouter.relay_voice(frame, ws, client)
                           └─ vc.ws.send(s2c_frame) for each voice peer
```

**Key invariant:** `MessageRouter` handlers always return the (possibly updated)
`client` object. Auth sets it from `None` to a `ConnectedClient`.

---

### client/

The client combines Textual (TUI framework) with WebSocket I/O. Both run on the
**same asyncio event loop** — Textual owns the loop and the worker coroutine is
scheduled on it via `app.run_worker()`.

#### Startup sequence

```
python -m client.main
  └─ TraxusApp.run()
       └─ on_mount()  →  push LoginScreen
            └─ user fills form → connect_to_server(url, username)
                 └─ WsWorker.run(url, username) scheduled as asyncio Task
                      └─ AUTH sent → auth_ok → switch_screen(ChatScreen)
```

#### Key files

| File | Class | Responsibility |
|---|---|---|
| `app.py` | `TraxusApp` | Root `App`; owns reactive state, routes server messages to ChatScreen |
| `ws_worker.py` | `WsWorker` | Three asyncio loops: recv, send, ping; posts messages to app |
| `audio_engine.py` | `AudioEngine` | Microphone capture + speaker playback |
| `commands.py` | — | `parse_input()` → `ParsedCommand`; `HELP_TEXT` |
| `screens/login_screen.py` | `LoginScreen` | Server URL + username form |
| `screens/chat_screen.py` | `ChatScreen` | Main chat view; delegates display to widgets |
| `widgets/channel_sidebar.py` | `ChannelSidebar` | Left panel — text and voice channels |
| `widgets/message_view.py` | `MessageView` | Scrolling `RichLog` of chat messages |
| `widgets/input_bar.py` | `InputBar` | Single-line `Input` widget at the bottom |
| `widgets/status_bar.py` | `StatusBar` | Connection state, nick, latency, PTT indicator |

#### Message flow (client side)

```
WebSocket frame
  └─ WsWorker._recv_loop
       ├─ bytes  → app.post_message(TraxusApp.AudioFrame(data))
       │             └─ on_traxus_app_audio_frame → AudioEngine.play()
       └─ str    → app.post_message(TraxusApp.ServerMessage(payload))
                     └─ on_traxus_app_server_message → match payload["type"]
                          └─ ChatScreen.append_chat / update_channel_list / …

User keystroke / command
  └─ InputBar  →  app.handle_input(text)
       ├─ plain text → WsWorker.enqueue({type: C2S.MESSAGE, …})
       └─ /command  → TraxusApp._execute_command(ParsedCommand)
                        └─ WsWorker.enqueue({type: C2S.*, …})
```

#### Reactive state (TraxusApp)

| Reactive | Type | Updated by |
|---|---|---|
| `connection_state` | `str` | `WsWorker` via `ConnectionStateChanged` |
| `current_channel` | `str` | `joined` server message |
| `current_voice_channel` | `str` | `voice_state` server message |
| `username` | `str` | `auth_ok` and `nick_changed` messages |

---

### Audio / PTT subsystem

PTT is bound at the **App level** with `priority=True` so it fires before any
focused widget (including the `Input` bar) consumes the key.

```python
BINDINGS = [Binding("f9", "ptt_toggle", "Toggle PTT", priority=True)]
```

**Capture path (F9 pressed)**

```
action_ptt_toggle()
  └─ AudioEngine.transmitting = True
       └─ sd.InputStream callback (audio thread)
            └─ loop.call_soon_threadsafe(queue.put_nowait, pcm)
                 └─ capture_loop coroutine  →  WsWorker.enqueue_binary(frame)
```

**Playback path (audio frame received)**

```
WsWorker._recv_loop → TraxusApp.AudioFrame posted
  └─ on_traxus_app_audio_frame (Textual pump, sync handler)
       └─ AudioEngine.play(pcm_bytes)  ← queue.put_nowait, returns in ~4 µs
            └─ _playback_worker thread  ← sd.OutputStream.write() (blocking, off-pump)
```

**Critical:** `play()` must never block the Textual message pump. The single
`sd.OutputStream` is owned by a daemon thread. Only `queue.put_nowait()` is
called on the pump — that takes nanoseconds.

---

## Design patterns

### 1. Textual + asyncio coexistence

Textual owns the asyncio event loop. Long-running async work is started with
`app.run_worker(coro)`. Worker coroutines can `await` freely; sync Textual
message handlers must complete quickly (no `await`, no blocking calls).

**Rule:** If a message handler does I/O or blocks, it will saturate the Textual
message pump and freeze the TUI for all connected clients.

### 2. Thread safety boundary

| Context | Allowed |
|---|---|
| Textual message pump (sync handlers) | `queue.put_nowait()`, attribute reads/writes |
| asyncio coroutines | `await queue.get()`, `ws.send()`, `loop.call_soon_threadsafe()` |
| sounddevice audio thread | `loop.call_soon_threadsafe(asyncio_queue.put_nowait, data)` |
| playback daemon thread | `threading_queue.get()` (blocking), `sd.OutputStream.write()` |

### 3. Guard against screen lifecycle errors

`self.screen` raises `ScreenStackError` when the screen stack is empty (during
shutdown). `query_one(...)` raises `NoMatches` when a widget is mid-teardown.
Wrap both in `try/except` and return `None`.

```python
def _chat(self) -> ChatScreen | None:
    try:
        screen = self.screen
    except Exception:
        return None
    return screen if isinstance(screen, ChatScreen) else None
```

### 4. Shared constants, not magic strings

All WebSocket message type strings live in `shared/message_types.py` as class
attributes (`C2S.*`, `S2C.*`, `ErrorCode.*`). Use these everywhere — never
hardcode the raw string in server or client code.

### 5. Graceful audio degradation

`AUDIO_AVAILABLE` is set at import time based on whether `sounddevice` and
`numpy` are importable. Every voice code path checks this flag and shows a user
message instead of crashing when the flag is `False`.

---

## Running the project

```bash
# Server
python -m server.main

# Client (separate terminal)
python -m client.main
```

Python 3.14 is the target interpreter (`python` on PATH). Voice requires
`sounddevice` and `numpy` (`pip install sounddevice numpy`).

---

## Test suite

The test suite uses **`unittest`** (stdlib). Run it with:

```bash
python -m unittest discover -s tests -v
```

Do **not** use pytest. All test classes extend `unittest.TestCase` (or
`unittest.IsolatedAsyncioTestCase` for async tests). New tests must follow the
same pattern.

| Test file | What it covers |
|---|---|
| `test_app.py` | Unit tests for TraxusApp including `TestPttF9Binding` (5 tests) |
| `test_channel_registry.py` | ChannelRegistry CRUD and validation |
| `test_commands.py` | `parse_input()` for all slash commands |
| `test_connection_manager.py` | ConnectedClient registration, broadcast, nick change |
| `test_message_router.py` | MessageRouter dispatch for every C2S message type |
| `test_message_view_utils.py` | Rich markup formatting helpers |
| `test_multiclient_ptt.py` | Multi-client audio relay; Textual pump latency during burst |
| `test_ptt_e2e.py` | Full integration: real server subprocess + Textual pilot |
| `test_voice_protocol.py` | Binary frame pack/unpack round-trip |

**Mandatory:** every edit must leave `python -m unittest discover -s tests -v` fully green.
