# Traxus — Slash Command Reference

This document covers every slash command available in the Traxus terminal client. For the underlying WebSocket messages each command sends and receives, see [protocol.md](protocol.md). For server-side validation rules, see [server-rules.md](server-rules.md).

---

## Parsing Rules

The client treats any input starting with `/` as a slash command. Parsing is done in `client/commands.py` by `parse_input()`:

| Rule | Detail |
|---|---|
| **Trigger** | Input must start with `/` after stripping leading/trailing whitespace |
| **Command name** | First token after `/`, **lowercased** (e.g. `/JOIN` → `join`) |
| **Arguments** | Remaining whitespace-separated tokens, **case preserved** |
| **Bare `/`** | Returns no command; treated as a no-op |
| **`/ ` (slash + spaces)** | Returns no command; treated as a no-op |
| **Unknown command** | Shows a local error message; **nothing is sent to the server** |
| **Plain text** | Any input not starting with `/` is sent as a chat `message` to the current channel |

---

## /join

Switch to an existing channel.

```
/join <channel>
/join #<channel>
```

| Argument | Required | Description |
|---|---|---|
| `channel` | Yes | Channel name. A leading `#` is stripped automatically. |

**Client effect:** Strips any `#` prefix, then sends `C2S join` to the server.

**If no argument is given:** Displays a local usage hint (`/join <channel>`) without sending anything to the server.

**C2S message sent:**
```json
{ "type": "join", "channel": "general" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `joined` | Sent to the joining client with channel history |
| `user_list` | Sent to the joining client with current members |
| `system` | Broadcast to all other members of the channel announcing the join |
| `channel_list` | *(Not re-sent on join; only on auth and create)* |

**Error responses:**

| Condition | S2C `error.code` |
|---|---|
| Channel does not exist | `no_such_channel` |

---

## /leave

Leave a channel you are currently in.

```
/leave [channel]
/leave #[channel]
```

| Argument | Required | Description |
|---|---|---|
| `channel` | No | Channel to leave. Defaults to the **current active channel** if omitted. A leading `#` is stripped. |

**Client effect:** Sends `C2S leave` for the specified (or current) channel.

**C2S message sent:**
```json
{ "type": "leave", "channel": "random" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `left` | Sent only to the leaving client confirming departure |
| `system` | Broadcast to remaining members of the channel announcing the leave |

**Edge case:** If you send `leave` for a channel you are not in, the server ignores it (no response).

---

## /nick

Change your display name.

```
/nick <new_name>
```

| Argument | Required | Description |
|---|---|---|
| `new_name` | Yes | New username. 1–32 characters, no spaces. |

**Client effect:** Sends `C2S nick` with the new name. The argument is passed exactly as typed (case preserved).

**If no argument is given:** Displays a local usage hint (`/nick <new_name>`) without sending anything.

**C2S message sent:**
```json
{ "type": "nick", "new_nick": "alice_dev" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `nick_changed` | Broadcast to **all connected clients** with old and new nick |

The client automatically updates its local display when it receives `nick_changed` for its own `user_id`.

**Error responses:**

| Condition | S2C `error.code` |
|---|---|
| Nick already taken by another user | `nick_taken` |
| Nick is empty, contains a space, or exceeds 32 chars | `invalid_channel_name` *(reuses validation code)* |

---

## /channels

List all available channels on the server.

```
/channels
```

No arguments.

**Client effect:** Sends `C2S list_channels`. The server responds with a fresh `channel_list` which the client uses to refresh the sidebar.

**C2S message sent:**
```json
{ "type": "list_channels" }
```

**S2C responses:**

| Type | When |
|---|---|
| `channel_list` | Sent only to this client with all current channels |

---

## /create

Create a new channel.

```
/create <name>
/create #<name>
```

| Argument | Required | Description |
|---|---|---|
| `name` | Yes | Channel name. Must match `^[a-z0-9_-]{1,32}$`. A leading `#` is stripped. |

**Client effect:** Strips any `#` prefix, then sends `C2S create`.

**If no argument is given:** Displays a local usage hint (`/create <channel-name>`) without sending anything.

**C2S message sent:**
```json
{ "type": "create", "channel": "my-channel" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `channel_created` | Broadcast to **all connected clients** |
| `channel_list` | Broadcast to **all connected clients** (updated list) |

**Error responses:**

| Condition | S2C `error.code` |
|---|---|
| Channel name fails regex validation | `invalid_channel_name` |
| Channel already exists | `channel_exists` |

---

## /help

Display the command reference locally.

```
/help
```

No arguments.

**Client effect:** Prints the built-in `HELP_TEXT` string to the message view in the current channel. **Nothing is sent to the server.**

**Output (local only):**
```
  /join <channel>     Join or switch to a channel
  /leave <channel>    Leave a channel
  /nick <name>        Change your display name
  /channels           List all available channels
  /create <name>      Create a new channel
  /help               Show this help
  /quit               Disconnect and exit
```

---

## /quit

Disconnect from the server and exit the client.

```
/quit
```

No arguments.

**Client effect:** Stops the WebSocket worker (closes the connection) and calls `app.exit()` to terminate the Textual TUI. The server detects the WebSocket close and broadcasts a disconnect notice to channels the user was in.

**Nothing is sent to the server** as an explicit message — the WebSocket close frame signals the departure.

---

## /vcreate

Create a new voice channel.

```
/vcreate <name>
/vcreate #<name>
```

| Argument | Required | Description |
|---|---|---|
| `name` | Yes | Channel name. Must match `^[a-z0-9_-]{1,32}$`. A leading `#` is stripped. |

**Client effect:** Strips any `#` prefix, then sends `C2S create` with `channel_type: "voice"`.

**If no argument is given:** Displays a local usage hint without sending anything.

**C2S message sent:**
```json
{ "type": "create", "channel": "lounge", "channel_type": "voice" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `channel_created` | Broadcast to **all connected clients** |
| `channel_list` | Broadcast to **all connected clients** (updated list, includes `type: "voice"`) |

**Error responses:**

| Condition | S2C `error.code` |
|---|---|
| Channel name fails regex validation | `invalid_channel_name` |
| Channel already exists | `channel_exists` |

---

## /vjoin

Join a voice channel and begin receiving audio.

```
/vjoin <channel>
/vjoin #<channel>
```

| Argument | Required | Description |
|---|---|---|
| `channel` | Yes | Voice channel name. Leading `#` stripped. |

**Client effect:** Sends `C2S voice_join`. Requires `sounddevice` to be installed; if unavailable shows a local error.

**C2S message sent:**
```json
{ "type": "voice_join", "channel": "lounge" }
```

**S2C responses (success):**

| Type | When |
|---|---|
| `voice_state` | Sent to all current voice members (including the joining client) with the updated member list |

**Error responses:**

| Condition | S2C `error.code` |
|---|---|
| Channel does not exist | `no_such_channel` |
| Channel exists but is a text channel | `not_a_voice_channel` |

---

## /vleave

Leave the current (or specified) voice channel.

```
/vleave [channel]
/vleave #[channel]
```

| Argument | Required | Description |
|---|---|---|
| `channel` | No | Channel to leave. Defaults to the current voice channel if omitted. Leading `#` stripped. |

**Client effect:** Sends `C2S voice_leave`. Requires `sounddevice` to be installed.

**C2S message sent:**
```json
{ "type": "voice_leave", "channel": "lounge" }
```

**S2C responses:**

| Type | When |
|---|---|
| `voice_state` | Sent to remaining voice members with the updated (smaller) member list |

---

## Push-to-Talk (PTT) — F9

Toggle microphone transmission on/off while in a voice channel.

| Input | Action |
|---|---|
| `F9` | Toggle PTT — starts or stops sending mic audio to the voice channel |

**Requirements:** Must be joined to a voice channel with `/vjoin` first. `sounddevice` and `numpy` must be installed.

**Status bar:** When PTT is active, the status bar shows `● MIC` in red.

**Note:** This is toggle mode (not hold-to-talk). `F9` is a priority binding that fires regardless of which widget is focused.
