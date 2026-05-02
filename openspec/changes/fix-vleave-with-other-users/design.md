## Context

When a client sends `VOICE_LEAVE`, `_handle_voice_leave` in `server/message_router.py`:
1. Removes the client from its `voice_channels` set
2. Builds `members` = remaining participants (excluding the leaver)
3. Broadcasts `{type: VOICE_STATE, channel: ch, users: members}` to remaining clients
4. Sends the **same message** to the leaving client

The leaving client's `voice_state` handler does:
```python
self.current_voice_channel = channel if users else ""
```
When `users` is non-empty (other participants remain), `current_voice_channel` stays set.
`_handle_voice_state_webrtc` is then called with the raw `channel` from the payload, so:
```python
left_voice = not bool(channel) and bool(prev_channel)  # False — channel is "lounge"
```
`close_all()` is never called; `_peer_manager` is never set to `None`; the UI still shows the user as in voice; PTT stays armed; re-joining later creates a second PeerManager over an existing one.

## Goals / Non-Goals

**Goals:**
- `/vleave` clears voice state and closes WebRTC connections for the leaving client regardless of how many participants remain
- Re-joining after `/vleave` works correctly

**Non-Goals:**
- Changing the message sent to remaining participants (they already receive the correct roster)
- Adding a new protocol message type (keep the change minimal)
- Handling edge cases like network-drop disconnects (separate concern)

## Decisions

### D1: Server sends `users=[]` to the leaving client

The leaving client needs to know it has departed. The simplest signal is sending it an empty `users` list while keeping `channel` set (for logging/diagnostics). This preserves the existing `channel if users else ""` client logic without any client-side protocol changes.

Alternative considered: send `channel=""` to the leaving client. Rejected — `""` loses the channel name and is semantically ambiguous with "you were never in a channel".

Alternative considered: add a dedicated `VOICE_LEFT` server-to-client message. Rejected — adds protocol complexity for a one-line server fix.

### D2: Client passes `self.current_voice_channel` (not raw `channel`) to `_handle_voice_state_webrtc`

After `self.current_voice_channel = channel if users else ""` is evaluated, `self.current_voice_channel` is `""` for the leaving client (because `users=[]`). Passing this updated value (instead of the payload's `channel`) means:

```python
left_voice = not bool("") and bool("lounge")  # True ✓
```

`close_all()` is called, `_peer_manager = None`, mic stream and output stream are closed cleanly.

The call currently passes `channel` (the raw payload field). Replacing it with `self.current_voice_channel` is a one-character-diff change that makes the argument semantically match what `_handle_voice_state_webrtc` actually needs: the *effective* channel after the reactive update.

## Risks / Trade-offs

- **Existing test `test_voice_state_clears_channel_when_self_not_in_users`**: already documents the intended behaviour correctly (it asserts `current_voice_channel == "lounge"` when `users=[bob]`, which is right — only the leaving client gets `users=[]`). No change needed to that test's assertion.
- **Protocol coupling**: remaining clients still receive the full roster; only the leaving client gets the empty list. This is asymmetric but correct — the two audiences need different information.
- **Race between server change and client change**: both must be deployed together, but since this is a single-process app (server and client in the same repo), there is no deployment race.

## Migration Plan

No schema changes. No settings changes. Deploy server + client together as a single commit. No rollback complexity.
