# Traxus — Server Business Rules

This document describes the validation constraints, auth guard, broadcast scope, and state invariants enforced by the Traxus server. These rules are implemented in `server/message_router.py`, `server/channel_registry.py`, and `server/connection_manager.py`.

For the JSON message shapes these rules apply to, see [protocol.md](protocol.md). For client-side command parsing, see [commands.md](commands.md).

---

## Auth Guard

**Every message type except `auth` requires a prior successful authentication.**

If the server receives any other message type from a WebSocket connection that has not yet completed `auth`, it responds immediately with:

```json
{ "type": "error", "code": "not_authenticated", "message": "Send auth first." }
```

The connection is kept open; the client may still send a valid `auth` message.

### Password Verification (auth mode)

When `TRAXUS_USERS` is set to a valid credentials file path, the server additionally verifies the `password` field of every `auth` message using bcrypt:

- **Correct password** → auth proceeds normally.
- **Wrong or missing password** → `auth_error { reason: "wrong_password" }` and connection close.
- **Unknown username** → also returns `wrong_password` (no enumeration).

When `TRAXUS_USERS` is unset or the file is absent, password verification is skipped entirely (no-auth mode — existing behaviour preserved).

---

## Username Validation (on `auth`)

| Rule | Constraint |
|---|---|
| Minimum length | 1 character (after stripping whitespace) |
| Maximum length | 32 characters |
| Spaces | Not allowed |
| Uniqueness | Must not be currently in use by another connected client |

**Failure responses:**

| Condition | `auth_error.reason` |
|---|---|
| Empty, >32 chars, or contains space | `invalid_username` |
| Already taken by another connected client | `username_taken` |

On `auth_error` the connection stays open; the client may retry with a different username.

---

## Nick Change Validation (on `nick`)

| Rule | Constraint |
|---|---|
| Minimum length | 1 character (after stripping whitespace) |
| Maximum length | 32 characters |
| Spaces | Not allowed |
| Uniqueness | Must not be currently in use by another connected client |

**Failure responses:**

| Condition | `error.code` |
|---|---|
| Empty, >32 chars, or contains space | `invalid_channel_name` *(shared validation code)* |
| Already taken by another connected client | `nick_taken` |

On success, `nick_changed` is broadcast to **all connected clients** and the server's internal nick → user_id map is updated atomically.

---

## Channel Name Validation (on `create`)

Channel names must match the regular expression:

```
^[a-z0-9_-]{1,32}$
```

Concretely:
- Lowercase ASCII letters, digits, underscores (`_`), hyphens (`-`) only
- 1–32 characters
- No uppercase, no spaces, no special characters

A leading `#` in the `channel` field is stripped by the server before validation.

**Failure responses:**

| Condition | `error.code` |
|---|---|
| Name fails regex | `invalid_channel_name` |
| Channel already exists | `channel_exists` |

---

## Broadcast Scope

Different events are delivered to different sets of connected clients.

### Channel-scoped broadcasts

These messages are sent **only to members of the affected channel**:

| Event | S2C type | Notes |
|---|---|---|
| User joins a channel | `system` | Sent to all members *except* the joiner |
| User leaves a channel | `system` | Sent to all remaining members including the leaver's confirmation (`left` is unicast) |
| User disconnects | `system` | Sent to all members of each channel the user was in |
| Chat message | `chat` | Sent to all members including the sender |

### Global broadcasts (all connected clients)

These messages are sent to **every connected client** regardless of channel membership:

| Event | S2C type | Notes |
|---|---|---|
| Nick change | `nick_changed` | So all clients can update their local display |
| Channel created | `channel_created` | Announces the new channel |
| Channel list refresh | `channel_list` | Sent after `create` and after any disconnect |

### Unicast (single client only)

These messages are sent only to the client that triggered them:

| Event | S2C type |
|---|---|
| Successful auth | `auth_ok` |
| Auth failure | `auth_error` |
| Channel joined (history + membership) | `joined`, `user_list` |
| Channel left (confirmation) | `left` |
| Channel directory (on `list_channels`) | `channel_list` |
| Ping reply | `pong` |
| Error responses | `error` |

---

## State Invariants

### Default channels

The server bootstraps three channels on startup:

| Channel | Topic |
|---|---|
| `#general` | General chat |
| `#random` | Anything goes |
| `#dev` | Dev discussion |

These channels always exist; `create` on any of these names returns `channel_exists`.

### Auto-join on auth

After a successful `auth`, the server **automatically joins the client to `#general`** without requiring an explicit `join` message. The client receives:

1. `joined` with `#general` history
2. `user_list` for `#general`
3. `channel_list` (full directory)

### Message history cap

Each channel maintains an in-memory ring buffer of the last **50 messages** (`MAX_HISTORY = 50` in `server/channel_registry.py`). Older messages are evicted automatically. This history is sent to any client that joins the channel (via the `history` array in the `joined` message).

History is **not persisted** — it resets when the server restarts.

### Disconnect cleanup sequence

When a WebSocket connection closes (clean or error):

1. The server removes the client from `ConnectionManager` (freeing the username).
2. For each **text** channel the client was a member of, the server broadcasts a `system` message: `"<username> disconnected"`.
3. For each **voice** channel the client was a member of, the server sends an updated `voice_state` to the remaining voice members (without the disconnected client).
4. The server broadcasts an updated `channel_list` to all remaining clients (member counts change).

This sequence is idempotent for `None` clients (connections that never completed auth are silently cleaned up).

---

## Voice Channel Rules

### Channel type validation (on `voice_join`)

A `voice_join` message is only accepted for channels with `type: "voice"`.

| Condition | `error.code` |
|---|---|
| Channel does not exist | `no_such_channel` |
| Channel exists but has `type: "text"` | `not_a_voice_channel` |

### Voice channel creation (on `create` with `channel_type: "voice"`)

Voice channels use the same name validation regex as text channels (`^[a-z0-9_-]{1,32}$`). A `channel_type: "voice"` field in the `create` payload causes the server to create a `type: "voice"` channel.

### Broadcast scope — voice events

| Event | S2C type | Recipients |
|---|---|---|
| Voice join | `voice_state` | All current voice members of the channel (including the joiner) |
| Voice leave | `voice_state` (to leaver) | The leaving client only — `users: []` always, regardless of remaining participants |
| Voice leave | `voice_state` (to remaining) | Remaining voice members — `users` lists everyone still present |
| Disconnect (was in voice) | `voice_state` | Remaining voice members of each voice channel |
| `voice_offer` / `voice_answer` / `voice_ice` | unicast to `to_user` | Only the named target peer |

**Note:** Audio data never passes through the server. Once WebRTC peers complete
ICE negotiation, RTP audio flows directly between clients. The server only
relays the three JSON signaling message types above. Binary WebSocket frames are
silently ignored.

### `channel_list` type field

The `channel_list` payload now includes a `"type"` field in each channel summary:

```json
{ "name": "lounge", "topic": "", "member_count": 2, "type": "voice" }
```

Existing text channels have `"type": "text"`.

### Nick uniqueness invariant

`ConnectionManager` maintains a `nick → user_id` map. At all times, no two connected clients share the same username. The map is updated atomically within the single-threaded asyncio event loop — no locks are required.
