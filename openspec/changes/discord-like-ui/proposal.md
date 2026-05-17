## Why

The current UI reflects implementation structure rather than user mental model: the right panel shows only the members of whichever channel the user happens to be in, and voice channels in the sidebar give no indication of who is present. Discord's established convention — a server-wide member roster on the right, voice occupants nested under the channel on the left — is immediately legible to new users and provides better at-a-glance situational awareness.

## What Changes

- **Right panel** replaces the current per-channel `MemberPanel` with a server-wide roster split into `ONLINE` and `OFFLINE` sections. Voice-active users gain an inline volume icon + percentage (`🔇/🔈/🔉/🔊 N%`). Navigation (↑/↓) and volume adjustment (←/→) are preserved as keyboard shortcuts.
- **Left sidebar** voice channels gain an indented member list below the channel name showing who is currently in that voice channel. Text channels remain unchanged (no nesting).
- **Server broadcasts global presence events** — `user_online` / `user_offline` — to all connected clients when any client connects or disconnects.
- **`auth_ok` response** includes an `online_users` snapshot and, when auth is enabled, a `known_users` list (registered users who may be offline).
- **`channel_list` response** gains a `voice_members` field per voice channel and is re-broadcast to all clients whenever voice membership changes.

## Capabilities

### New Capabilities

- `global-presence`: Server broadcasts `user_online`/`user_offline` events and includes `online_users`/`known_users` in `auth_ok`. Client maintains a server-wide roster of online and known-offline users.
- `voice-channel-occupancy`: `channel_list` entries for voice channels include a `voice_members` array. Server re-broadcasts `channel_list` to all clients on any voice join/leave. Client sidebar renders nested member rows under voice channels.
- `server-member-panel`: Right panel redesigned to show all server members in Online/Offline sections with per-voice-user volume indicator (icon + percentage, read-only display; ←/→ to adjust).

### Modified Capabilities

- `member-list-panel`: Requirements change — panel now shows server-wide roster (not channel-scoped), adds Online/Offline sections, replaces the volume bar widget with an icon+percentage display.
- `per-participant-volume`: Volume indicator moves from a standalone bar widget to an inline `🔇/🔈/🔉/🔊 N%` display. Keyboard UX (←/→ to adjust) is preserved; the bar graphic is removed.
- `webrtc-signaling-protocol`: `channel_list` gains `voice_members` per voice channel; new `user_online`/`user_offline` message types added to the protocol.
- `websocket-protocol-reference`: New S2C message types (`user_online`, `user_offline`) and updated `auth_ok` / `channel_list` field specs.

## Impact

- **`shared/message_types.py`** — two new `S2C` constants
- **`server/connection_manager.py`** — broadcast presence events on connect/disconnect; include user snapshot in `auth_ok`
- **`server/channel_registry.py`** — expose `voice_members` per channel; trigger `channel_list` rebroadcast on voice state change
- **`server/message_router.py`** — hook voice join/leave to trigger rebroadcast
- **`client/widgets/member_panel.py`** — rewritten for server-wide roster
- **`client/widgets/channel_sidebar.py`** — render nested voice members
- **`client/screens/chat_screen.py`** — new `update_server_members()` helper
- **`client/app.py`** — handle `user_online`/`user_offline`; populate roster from `auth_ok`
- No new dependencies; no breaking changes to the text-chat or WebRTC audio path
