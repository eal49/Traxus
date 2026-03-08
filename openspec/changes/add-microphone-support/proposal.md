## Why

Traxus is modelled on Discord/TeamSpeak but currently supports only text channels. Adding real-time voice communication is the single largest gap between Traxus and its inspiration: it lets users talk while they work instead of typing, which is the primary use-case for TeamSpeak-style tools.

## What Changes

- **New channel type `voice`** — channels carry a `type` field (`"text"` | `"voice"`); voice channels relay raw-PCM audio frames instead of chat messages.
- **Binary WebSocket frames** — audio data is transmitted as binary frames on the existing WebSocket connection, alongside the existing JSON text frames.
- **Push-to-talk (PTT) input** — Ctrl+M toggles mic transmission; the status bar shows a live `[● MIC]` indicator.
- **New C2S messages**: `voice_join`, `voice_leave`.
- **New S2C message**: `voice_state` (who is in a voice channel).
- **New slash commands**: `/vjoin <channel>`, `/vleave`, `/vcreate <name>`.
- **New dependencies**: `sounddevice`, `numpy` (audio capture and playback).

## Capabilities

### New Capabilities

- `voice-channels`: Real-time voice channel model — channel type field, voice membership tracking on server, voice_join/voice_leave C2S messages, voice_state S2C broadcast, binary audio frame relay.
- `audio-engine`: Client-side audio capture and playback — sounddevice InputStream/OutputStream, push-to-talk toggle, per-speaker playback, asyncio-safe callback bridging.

### Modified Capabilities

- `slash-command-reference`: Three new slash commands added (`/vjoin`, `/vleave`, `/vcreate`).
- `websocket-protocol-reference`: Two new C2S types, one new S2C type, and binary frame format added to transport section.
- `server-business-rules`: Voice channel validation rules and broadcast scope table updated.

## Impact

- `shared/message_types.py` — new C2S/S2C constants, new `ErrorCode` values.
- `shared/voice_protocol.py` *(new)* — binary frame pack/unpack helpers.
- `server/channel_registry.py` — `Channel.type` field, voice member tracking.
- `server/connection_manager.py` — voice channel membership per client.
- `server/message_router.py` — `voice_join`, `voice_leave`, `relay_voice` handlers; binary frame dispatch in `dispatch()`.
- `server/main.py` — route binary frames to `relay_voice` before JSON dispatch.
- `client/audio_engine.py` *(new)* — sounddevice capture/playback, PTT state.
- `client/ws_worker.py` — binary frame receive path, `enqueue_binary()`.
- `client/app.py` — PTT keybinding, new server message handlers.
- `client/commands.py` — `vjoin`, `vleave`, `vcreate` added to `KNOWN_COMMANDS`.
- `client/widgets/channel_sidebar.py` — voice channel visual distinction.
- `client/widgets/status_bar.py` — `[● MIC]` transmitting indicator.
- `requirements.txt` — `sounddevice>=0.4`, `numpy>=1.26`.
