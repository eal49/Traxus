# Traxus — WebSocket Protocol Reference

This document specifies every message type exchanged between Traxus clients and the Traxus server. For the client-side slash commands that trigger these messages, see [commands.md](commands.md). For server-side validation and business rules, see [server-rules.md](server-rules.md).

---

## Transport & Encoding

| Property | Value |
|---|---|
| Transport | WebSocket over TCP |
| Text encoding | UTF-8 |
| Frame types | **Text** frames (JSON messages) only — audio is transported over WebRTC |
| Text framing | One JSON object per text frame |
| Required field | Every JSON message **must** include a `"type"` string field |
| Server version | `0.2.0` (echoed in `auth_ok`; clients with a different version are rejected) |

### Audio Transport

Audio is transported peer-to-peer via **WebRTC** (aiortc). The WebSocket connection is used only for JSON signaling messages (`voice_offer`, `voice_answer`, `voice_ice`) that set up the WebRTC connection. Once the WebRTC data channel is established, audio flows directly between clients without passing through the server.

Audio parameters: `samplerate=16000`, `channels=1`, `dtype=int16`, `blocksize=320` samples (20 ms frames).

### WebRTC Signaling Flow

```
Alice (caller)                  Server                  Bob (callee)
     │                             │                         │
     │─── voice_join ─────────────▶│                         │
     │◀── voice_state (Alice) ─────│                         │
     │                             │◀── voice_join ──────────│
     │◀── voice_state (Alice,Bob) ─│─── voice_state ────────▶│
     │                             │    (Alice, Bob)          │
     │  Alice creates RTCPeerConnection, adds MicTrack        │
     │─── voice_offer {sdp, to:"Bob"} ───────────────────────▶│
     │                             │─── voice_offer ─────────▶│
     │                             │    {sdp, from:"Alice"}   │
     │  Bob creates RTCPeerConnection, adds MicTrack          │
     │◀──────────────────────────────── voice_answer ─────────│
     │    {sdp, to:"Alice"}        │◀── voice_answer ─────────│
     │                             │    {from:"Bob"}          │
     │◀══════════════════ ICE candidates (both directions) ═══│
     │                             │                         │
     │◀══════════════════ WebRTC audio (peer-to-peer) ════════│
```

The server relays `voice_offer`, `voice_answer`, and `voice_ice` messages by copying the payload and setting `from_user` to the sender's username. It does not inspect or modify the SDP or ICE candidate contents. Binary WebSocket frames are ignored (no-op).

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

> **Password auth:** When the server is configured with `TRAXUS_USERS`, the `auth` message must include a `password` field matching the stored bcrypt hash. A missing or incorrect password returns `auth_error { reason: "wrong_password" }` and closes the connection. When `TRAXUS_USERS` is unset, the `password` field is silently ignored.

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
| `version` | string | Yes | Client version string. Must match server version or auth is rejected with `version_mismatch`. |
| `password` | string | No | Password for the account. Required only when the server has `TRAXUS_USERS` configured; omit or leave empty for no-auth servers. |

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

### delete_channel

Delete a non-default text channel. Any user may delete a channel; the default channels (`general`, `random`, `dev`) are protected.

```json
{ "type": "delete_channel", "channel": "old-project" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"delete_channel"` |
| `channel` | string | Yes | Channel name to delete. Leading `#` stripped by the server. |

On success the server broadcasts `channel_deleted` and a fresh `channel_list` to all connected clients. Clients that were in the deleted channel should rejoin `#general`.

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

### change_password

Change the authenticated user's own password. Requires the server to have `TRAXUS_USERS` configured.

```json
{
  "type": "change_password",
  "old_password": "currentpassword",
  "new_password": "mynewpassword1"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"change_password"` |
| `old_password` | string | Yes | Current password for verification. |
| `new_password` | string | Yes | Desired new password. Minimum 10 characters. Must differ from `old_password`. |

**S2C responses:** `password_changed` on success, `password_change_error` on failure.

---

### voice_offer

Send a WebRTC SDP offer to a specific peer. The server relays it to the target user.

```json
{
  "type": "voice_offer",
  "to_user": "bob",
  "sdp": "<SDP offer string>"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"voice_offer"` |
| `to_user` | string | Yes | Username of the intended recipient. |
| `sdp` | string | Yes | SDP offer generated by `RTCPeerConnection.createOffer()`. |

---

### voice_answer

Send a WebRTC SDP answer in response to a `voice_offer`. The server relays it to the target user.

```json
{
  "type": "voice_answer",
  "to_user": "alice",
  "sdp": "<SDP answer string>"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"voice_answer"` |
| `to_user` | string | Yes | Username of the intended recipient (the original offerer). |
| `sdp` | string | Yes | SDP answer generated by `RTCPeerConnection.createAnswer()`. |

---

### voice_ice

Send an ICE candidate to a specific peer. The server relays it to the target user.

```json
{
  "type": "voice_ice",
  "to_user": "bob",
  "candidate": "candidate:...",
  "sdp_mid": "0",
  "sdp_mline_index": 0
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `"voice_ice"` |
| `to_user` | string | Yes | Username of the intended recipient. |
| `candidate` | string | Yes | ICE candidate string from the `icecandidate` event. |
| `sdp_mid` | string | Yes | Media stream identification tag. |
| `sdp_mline_index` | integer | Yes | Index of the associated m-line in the SDP. |

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
| `online_users` | array of strings | Usernames of all clients currently connected at the moment of authentication (includes the authenticating user). |
| `known_users` | array of strings | All registered usernames from the server's user store. When the server has no `TRAXUS_USERS` configured, equals `online_users`. |
| `must_change_password` | boolean | Present and `true` only when the server admin provisioned the account with a temporary password. The client should prompt the user to run `/passwd`. |

Immediately followed by `joined` (for `#general`) and `channel_list`. The server also broadcasts `user_online` to all previously connected clients at this point.

---

### auth_error

Authentication rejected.

```json
{ "type": "auth_error", "reason": "username_taken" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"auth_error"` |
| `reason` | string | See table below. |

**Reason values:**

| Reason | Meaning |
|---|---|
| `username_taken` | Another connected client already uses this username. Connection stays open; client may retry with a different name. |
| `invalid_username` | Username is empty, over 32 chars, or contains spaces. |
| `version_mismatch` | Client version does not match server version. Connection is closed. |
| `wrong_password` | Password missing or incorrect; also returned for unknown usernames to prevent enumeration. Connection is closed. |

---

### password_changed

The user's password was changed successfully. Sent in response to a `change_password` message.

```json
{ "type": "password_changed" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"password_changed"` |

The server also clears the `must_change` flag for the account. The client should dismiss any open password-change screen and clear the status bar nudge.

---

### password_change_error

The password change request was rejected. Sent in response to a `change_password` message.

```json
{
  "type": "password_change_error",
  "reason": "wrong_password"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"password_change_error"` |
| `reason` | string | Machine-readable reason (see table below). |

**Reason values:**

| Reason | Meaning |
|---|---|
| `wrong_password` | `old_password` did not match the stored credential. |
| `too_short` | `new_password` is fewer than 10 characters. |
| `same_password` | `new_password` is identical to the current password. |
| `auth_disabled` | The server has no `TRAXUS_USERS` store configured; password changes are not supported. |

---

### channel_list

Directory of all channels on the server.

```json
{
  "type": "channel_list",
  "channels": [
    { "name": "general", "topic": "General chat", "member_count": 3, "type": "text" },
    { "name": "lounge",  "topic": "Voice lounge", "member_count": 0, "type": "voice",
      "voice_members": ["alice", "bob"] }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"channel_list"` |
| `channels` | array | Array of channel summary objects. |
| `channels[].name` | string | Channel name. |
| `channels[].topic` | string | Channel topic (may be empty). |
| `channels[].member_count` | integer | Number of currently connected text-channel members. |
| `channels[].type` | string | `"text"` or `"voice"`. |
| `channels[].voice_members` | array of strings | **Voice channels only.** Usernames of all clients currently in the voice channel. Absent for text channels. |

Sent to: the requesting client on `auth` and `list_channels`; **broadcast to all clients** on `create`, `delete_channel`, on disconnect, and whenever voice membership changes (`voice_join`, `voice_leave`, or disconnect while in a voice channel).

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

### channel_deleted

Broadcast when a channel is deleted.

```json
{ "type": "channel_deleted", "channel": "old-project" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"channel_deleted"` |
| `channel` | string | Name of the deleted channel. |

Sent to: **all connected clients**. Always followed by a `channel_list` broadcast. Clients that were in the deleted channel should automatically rejoin `#general`.

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
| `cannot_delete_default_channel` | `delete_channel` targeting one of the three protected defaults (`general`, `random`, `dev`) |

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
| `users` | array | Array of `{ user_id, username }` objects for all current voice members. Empty array means no one is in the channel (or the recipient has just left). |

**Delivery after `voice_join`:** sent to all current voice members including the joiner; `users` lists everyone now in the channel.

**Delivery after `voice_leave`:** two separate deliveries:
- **Leaving client** — `users: []` (always empty), signalling unambiguous departure regardless of remaining participants.
- **Remaining members** — `users` lists everyone still in the channel (excludes the leaver).

**Delivery after disconnect:** remaining members only; `users` excludes the disconnected client.

---

### voice_offer (S2C)

A WebRTC SDP offer relayed from another peer. The server overwrites `from_user` with the sender's authenticated username.

```json
{
  "type": "voice_offer",
  "from_user": "alice",
  "sdp": "<SDP offer string>"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"voice_offer"` |
| `from_user` | string | Username of the peer who sent the offer (set by server). |
| `sdp` | string | SDP offer to pass to `RTCPeerConnection.setRemoteDescription()`. |

---

### voice_answer (S2C)

A WebRTC SDP answer relayed from another peer.

```json
{
  "type": "voice_answer",
  "from_user": "bob",
  "sdp": "<SDP answer string>"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"voice_answer"` |
| `from_user` | string | Username of the peer who sent the answer. |
| `sdp` | string | SDP answer to pass to `RTCPeerConnection.setRemoteDescription()`. |

---

### voice_ice (S2C)

A WebRTC ICE candidate relayed from another peer.

```json
{
  "type": "voice_ice",
  "from_user": "alice",
  "candidate": "candidate:...",
  "sdp_mid": "0",
  "sdp_mline_index": 0
}
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"voice_ice"` |
| `from_user` | string | Username of the peer who sent the candidate. |
| `candidate` | string | ICE candidate string. |
| `sdp_mid` | string | Media stream identification tag. |
| `sdp_mline_index` | integer | Index of the associated m-line in the SDP. |

---

### user_online

Broadcast to all currently connected clients (except the new user themselves) when a client authenticates successfully.

```json
{ "type": "user_online", "username": "bob" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"user_online"` |
| `username` | string | Display name of the newly connected user. |

Sent to: **all connected clients except the authenticating user**. Clients use this to move the user from the Offline section to the Online section of the member panel.

---

### user_offline

Broadcast to all remaining connected clients when a client disconnects (clean close or network failure).

```json
{ "type": "user_offline", "username": "bob" }
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"user_offline"` |
| `username` | string | Display name of the disconnected user. |

Sent to: **all remaining connected clients**. Triggered on both clean WebSocket close and abnormal disconnection. Clients use this to move the user from the Online section to the Offline section (if the user is a registered user known from `auth_ok`'s `known_users` list).

