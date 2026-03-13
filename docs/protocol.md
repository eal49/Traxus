# Traxus — WebSocket Protocol Reference

This document specifies every message type exchanged between Traxus clients and the Traxus server. For the client-side slash commands that trigger these messages, see [commands.md](commands.md). For server-side validation and business rules, see [server-rules.md](server-rules.md).

---

## Transport & Encoding

| Property | Value |
|---|---|
| Transport | WebSocket over TCP |
| Text encoding | UTF-8 |
| Frame types | **Text** frames (JSON messages) and **Binary** frames (audio) |
| Text framing | One JSON object per text frame |
| Required field | Every JSON message **must** include a `"type"` string field |
| Server version | `0.2.0` (echoed in `auth_ok`; clients with a different version are rejected) |

### Binary Audio Frames

Audio data is transmitted as WebSocket **binary frames** on the same connection as JSON text frames. The `websockets` library yields `str` for text frames and `bytes` for binary frames from the same iterator.

Each frame contains a **1-byte codec tag** immediately before the audio payload. The server relays binary frames transparently — it never inspects past the channel/username headers.

**Codec tag values:**

| Value | Constant | Meaning |
|-------|----------|---------|
| `0x00` | `CODEC_RAW` | Raw int16 LE PCM (fallback when numpy unavailable) |
| `0x01` | `CODEC_ADPCM` | IMA ADPCM compressed (~4× reduction, 256 kbps → ~64 kbps) |

**C2S binary frame (client → server):**
```
[1 byte : channel name length N]
[N bytes: channel name (UTF-8)]
[1 byte : codec tag (0x00 = raw PCM, 0x01 = IMA ADPCM)]
[remaining: audio payload]
```

**S2C binary frame (server → client):**
```
[1 byte : channel name length N]
[N bytes: channel name (UTF-8)]
[1 byte : username length M]
[M bytes: username (UTF-8)]
[1 byte : codec tag (0x00 = raw PCM, 0x01 = IMA ADPCM)]
[remaining: audio payload]
```

**IMA ADPCM payload format** (when codec tag = `0x01`):
```
[2 bytes: initial predictor (int16 LE)]
[2 bytes: initial step index (int16 LE, clamped to 0–88)]
[remaining: nibble-packed ADPCM samples, two 4-bit nibbles per byte, LSB first]
```

Audio parameters: `samplerate=16000`, `channels=1`, `dtype=int16`, `blocksize=320` samples (20 ms frames).

---

## Connection Lifecycle

```
Client                                    Server
  │                                          │
  │──── TCP + WebSocket handshake ──────────▶│
  │                                          │
  │──── C2S auth ───────────────────────────▶│  (must be first message)
  │◀─── S2C auth_ok ─────────────────────────│
  │◀─── S2C joined  { channel: "general" } ──│  (auto-join)
  │◀─── S2C user_list { channel: "general" } │
  │◀─── S2C channel_list ────────────────────│
  │                                          │
  │  ── Normal operation ─────────────────── │
  │                                          │
  │──── C2S message ────────────────────────▶│
  │◀─── S2C chat (broadcast to channel) ─────│
  │                                          │
  │──── C2S ping ───────────────────────────▶│
  │◀─── S2C pong ────────────────────────────│
  │                                          │
  │──── WebSocket close frame ──────────────▶│
  │                                          │  server unregisters client,
  │                                          │  broadcasts S2C system to channels
```

> **Auth guard:** The server rejects every message type except `auth` from an unauthenticated connection with `error { code: "not_authenticated" }`.

---

## Client → Server Messages (C2S)

### auth

First message sent after connecting. Must precede all other messages.

```json
{
  "type": "auth",
  "username": "alice",
  "client_version": "0.1.0"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"auth"` |
| `username` | string | Yes | Desired display name. 1–32 chars, no spaces, must be unique. |
| `client_version` | string | No | Client version string (currently unused by server). |

---

### join

Subscribe to an existing channel.

```json
{ "type": "join", "channel": "random" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"join"` |
| `channel` | string | Yes | Channel name. A leading `#` is stripped by the server. |

---

### leave

Unsubscribe from a channel.

```json
{ "type": "leave", "channel": "random" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"leave"` |
| `channel` | string | Yes | Channel name to leave. Leading `#` stripped. |

---

### message

Send a chat message to a channel.

```json
{
  "type": "message",
  "channel": "general",
  "content": "hello everyone"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"message"` |
| `channel` | string | Yes | Target channel name. Leading `#` stripped. |
| `content` | string | Yes | Message body. Empty strings are silently ignored. |

---

### nick

Change the client's display name.

```json
{ "type": "nick", "new_nick": "alice_dev" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"nick"` |
| `new_nick` | string | Yes | New display name. 1–32 chars, no spaces, must be unique. |

---

### create

Create a new channel.

```json
{ "type": "create", "channel": "my-channel" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"create"` |
| `channel` | string | Yes | New channel name. Must match `^[a-z0-9_-]{1,32}$`. Leading `#` stripped. |

---

### list_channels

Request a fresh channel directory from the server.

```json
{ "type": "list_channels" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"list_channels"` |

---

### ping

Keepalive heartbeat. The client sends this every 30 seconds.

```json
{ "type": "ping", "ts": 1741392000.123 }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"ping"` |
| `ts` | float | Yes | Client-side Unix timestamp (seconds). Echoed back in `pong` for latency calculation. |

---

### voice_join

Join a voice channel and begin participating in audio relay.

```json
{ "type": "voice_join", "channel": "lounge" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"voice_join"` |
| `channel` | string | Yes | Voice channel name. Leading `#` stripped by server. |

---

### voice_leave

Leave a voice channel and stop receiving/sending audio for it.

```json
{ "type": "voice_leave", "channel": "lounge" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"voice_leave"` |
| `channel` | string | Yes | Voice channel name. Leading `#` stripped by server. |

---

## Server → Client Messages (S2C)

### auth_ok

Authentication accepted.

```json
{
  "type": "auth_ok",
  "user_id": "a1b2c3d4-...",
  "username": "alice",
  "server_version": "0.1.0"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"auth_ok"` |
| `user_id` | string | UUID4 assigned to this connection. |
| `username` | string | Confirmed display name (matches the `auth` request). |
| `server_version` | string | Server version string. |

Immediately followed by `joined` (for `#general`) and `channel_list`.

---

### auth_error

Authentication rejected.

```json
{ "type": "auth_error", "reason": "username_taken" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"auth_error"` |
| `reason` | string | `"username_taken"` or `"invalid_username"` |

---

### channel_list

Directory of all channels on the server.

```json
{
  "type": "channel_list",
  "channels": [
    { "name": "general", "topic": "General chat", "member_count": 3 },
    { "name": "random",  "topic": "Anything goes", "member_count": 1 }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"channel_list"` |
| `channels` | array | Array of channel summary objects. |
| `channels[].name` | string | Channel name. |
| `channels[].topic` | string | Channel topic (may be empty). |
| `channels[].member_count` | integer | Number of currently connected members. |

Sent to: the requesting client on `auth` and `list_channels`; **broadcast to all clients** on `create` and on disconnect.

---

### joined

Confirms the client has entered a channel. Sent to the joining client only.

```json
{
  "type": "joined",
  "channel": "general",
  "history": [
    {
      "type": "chat",
      "channel": "general",
      "user_id": "...",
      "username": "bob",
      "content": "hey all",
      "ts": 1741391900.0
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"joined"` |
| `channel` | string | Channel name entered. |
| `history` | array | Last ≤50 `chat` messages from the channel's in-memory history. |

---

### left

Confirms the client has left a channel. Sent to the leaving client only.

```json
{ "type": "left", "channel": "random" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"left"` |
| `channel` | string | Channel name departed. |

---

### chat

A chat message broadcast to all members of a channel.

```json
{
  "type": "chat",
  "channel": "general",
  "user_id": "a1b2c3d4-...",
  "username": "alice",
  "content": "hello everyone",
  "ts": 1741392000.123
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"chat"` |
| `channel` | string | Channel the message was sent to. |
| `user_id` | string | Sender's UUID. |
| `username` | string | Sender's current display name. |
| `content` | string | Message body. |
| `ts` | float | Server Unix timestamp (seconds). |

Sent to: all members of the channel (including the sender).

---

### system

A server-generated informational notice.

```json
{
  "type": "system",
  "channel": "general",
  "content": "alice joined #general",
  "ts": 1741392000.123
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"system"` |
| `channel` | string | Channel the notice belongs to. |
| `content` | string | Human-readable message. |
| `ts` | float | Server Unix timestamp. |

Triggers: join, leave, disconnect. Sent to channel members (excluding the subject on join).

---

### nick_changed

Broadcast when any user changes their display name.

```json
{
  "type": "nick_changed",
  "old_nick": "alice",
  "new_nick": "alice_dev",
  "user_id": "a1b2c3d4-..."
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"nick_changed"` |
| `old_nick` | string | Previous display name. |
| `new_nick` | string | New display name. |
| `user_id` | string | UUID of the user who changed nick. |

Sent to: **all connected clients**.

---

### channel_created

Broadcast when a new channel is created.

```json
{
  "type": "channel_created",
  "channel": "my-channel",
  "created_by": "alice"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"channel_created"` |
| `channel` | string | Name of the new channel. |
| `created_by` | string | Display name of the creator. |

Sent to: **all connected clients**. Always followed by a `channel_list` broadcast.

---

### user_list

Members of a channel. Sent to the joining client immediately after `joined`.

```json
{
  "type": "user_list",
  "channel": "general",
  "users": [
    { "user_id": "a1b2c3d4-...", "username": "alice" },
    { "user_id": "b2c3d4e5-...", "username": "bob" }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"user_list"` |
| `channel` | string | Channel this list applies to. |
| `users` | array | Array of `{ user_id, username }` objects. |

**Client handling:** The client uses this message to populate the right-side member panel for the specified channel. Between `user_list` deliveries, the client tracks membership changes incrementally from `system` join/leave/disconnect messages and `nick_changed` broadcasts.

---

### error

Generic error response.

```json
{
  "type": "error",
  "code": "no_such_channel",
  "message": "Channel #nope does not exist."
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"error"` |
| `code` | string | Machine-readable error code (see table below). |
| `message` | string | Human-readable description. |

**Error codes:**

| Code | Trigger |
|---|---|
| `not_authenticated` | Any non-`auth` message sent before authentication |
| `invalid_json` | Malformed JSON received |
| `unknown_message_type` | Unrecognised `type` field |
| `no_such_channel` | `join` or `message` targeting a non-existent channel |
| `channel_exists` | `create` targeting an already-existing channel |
| `nick_taken` | `nick` where the new name is already in use |
| `invalid_channel_name` | `create` with an invalid name; also used for invalid `nick` values |
| `not_a_voice_channel` | `voice_join` targeting a channel that exists but has `type: "text"` |

---

### pong

Reply to a `ping`.

```json
{ "type": "pong", "ts": 1741392000.123 }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"pong"` |
| `ts` | float | The `ts` value echoed from the client's `ping`. |

The client calculates round-trip latency as `(time.time() - ts) * 1000` ms.

---

### voice_state

Current membership of a voice channel. Sent after every `voice_join`, `voice_leave`, and on disconnect cleanup.

```json
{
  "type": "voice_state",
  "channel": "lounge",
  "users": [
    { "user_id": "a1b2c3d4-...", "username": "alice" },
    { "user_id": "b2c3d4e5-...", "username": "bob" }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"voice_state"` |
| `channel` | string | Voice channel this state applies to. |
| `users` | array | Array of `{ user_id, username }` objects for all current voice members. Empty array means no one is in the channel. |

Sent to: all current voice members of the channel (after join: includes the joiner; after leave/disconnect: does not include the departed user).

---

**Updated error codes** (additions to the existing error table):

| Code | Trigger |
|---|---|
| `not_a_voice_channel` | `voice_join` targeting a text channel |
