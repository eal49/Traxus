## 1. Shared Protocol Constants

- [x] 1.1 Add `S2C.USER_ONLINE = "user_online"` and `S2C.USER_OFFLINE = "user_offline"` to `shared/message_types.py`

## 2. Server — Global Presence

- [x] 2.1 In `ConnectionManager`, add a helper `broadcast_to_all_except(payload, exclude_ws)` that sends to every connected client except the named one
- [x] 2.2 In `ConnectionManager.register()` (or equivalent auth-success path in `MessageRouter`), broadcast `user_online` to all other clients after successful auth
- [x] 2.3 In `ConnectionManager.unregister()` (or disconnect cleanup), broadcast `user_offline` to all remaining clients
- [x] 2.4 In the `auth_ok` response, include `online_users` (list of all currently connected usernames) and `known_users` (usernames from `AuthStore` if auth is enabled, else same as `online_users`)

## 3. Server — Voice Channel Occupancy in channel_list

- [x] 3.1 In `ChannelRegistry`, update the channel-list serialiser to include `"voice_members": [...]` for each voice channel entry
- [x] 3.2 Add a `broadcast_channel_list(connection_manager)` helper to `ChannelRegistry` (or `MessageRouter`) that sends the full updated `channel_list` to every connected client
- [x] 3.3 Call `broadcast_channel_list` at the end of the `voice_join` handler (after updating voice membership)
- [x] 3.4 Call `broadcast_channel_list` at the end of the `voice_leave` handler
- [x] 3.5 Call `broadcast_channel_list` when a client disconnects while in a voice channel

## 4. Server Tests

- [x] 4.1 Add tests to `test_connection_manager.py` verifying `user_online` is broadcast to peers on auth and `user_offline` is broadcast on disconnect
- [x] 4.2 Add tests to `test_channel_registry.py` (or `test_message_router.py`) verifying `channel_list` entries include `voice_members` and are rebroadcast on voice join/leave/disconnect
- [x] 4.3 Add a test verifying `auth_ok` payload includes `online_users` and `known_users`

## 5. Client — Global Presence State

- [x] 5.1 In `TraxusApp.on_mount`, initialise `_online_users: set[str]` and `_known_offline_users: set[str]`
- [x] 5.2 In the `auth_ok` handler, populate `_online_users` from `payload["online_users"]` and `_known_offline_users` from `set(payload.get("known_users", [])) - _online_users`
- [x] 5.3 Add a `user_online` message handler: add username to `_online_users`, remove from `_known_offline_users`, refresh right panel
- [x] 5.4 Add a `user_offline` message handler: remove username from `_online_users`, add to `_known_offline_users` if it was previously known, refresh right panel
- [x] 5.5 Pass `_online_users` and `_known_offline_users` to `ChatScreen.update_server_members()` after each change

## 6. Client — MemberPanel Rewrite (Right Panel)

- [x] 6.1 Replace `MemberPanel._members` (channel-scoped list) with `_online: list[str]` and `_offline: list[str]` fed by the server roster
- [x] 6.2 Add `set_server_members(online, offline)` public method replacing `set_members()`
- [x] 6.3 Replace `_volume_bar()` helper with `_volume_icon(level: int) -> str` returning `🔇/🔈/🔉/🔊` based on tier thresholds (0, 1–50, 51–149, 150–200)
- [x] 6.4 Rewrite `_build_markup()` to render `ONLINE — N` section (online users, voice users get `icon N%`), then `OFFLINE — N` section (dim style) if non-empty
- [x] 6.5 Update ↑/↓ cursor navigation to iterate only over voice-active users within the Online section
- [x] 6.6 Keep ←/→ volume adjustment logic unchanged (calls `PeerManager.set_volume`); update the re-render to use the new icon format

## 7. Client — ChatScreen Wiring

- [x] 7.1 Add `update_server_members(online: list[str], offline: list[str])` to `ChatScreen`; wire it to `MemberPanel.set_server_members()`
- [x] 7.2 Remove or repurpose the `update_members()` call that previously passed channel-scoped `user_list` members to the right panel (channel membership no longer drives the right panel)
- [x] 7.3 Ensure `update_member_voice()` (called on `voice_state`) still passes voice users to `MemberPanel.update_voice()` so the volume indicators appear correctly

## 8. Client — ChannelSidebar Voice Nesting

- [x] 8.1 Update `ChannelSidebar.refresh_channels()` to read `ch.get("voice_members", [])` from each voice channel dict
- [x] 8.2 For each voice channel, append non-interactive `ListItem` rows (one per member, indented with `  · `) immediately after the channel's own row; mark them with `can_focus = False`
- [x] 8.3 Ensure these nested rows do not emit `ChannelSelected` messages when clicked

## 9. Client Tests

- [x] 9.1 Update `test_member_panel.py`: replace channel-member tests with server-roster tests (Online/Offline sections, voice icon tiers, navigation skips non-voice rows)
- [x] 9.2 Add tests for `_volume_icon()` covering all four tiers and boundary values
- [x] 9.3 Update `test_app.py`: add tests for `user_online` / `user_offline` handler updating the roster sets
- [x] 9.4 Update `test_channel_registry.py` or add a new test verifying the sidebar renders voice member nesting from `channel_list` `voice_members`

## 10. Documentation

- [x] 10.1 Update `docs/protocol.md`: add `user_online` and `user_offline` S2C entries with field tables
- [x] 10.2 Update `docs/protocol.md`: document `online_users` and `known_users` fields on `auth_ok`
- [x] 10.3 Update `docs/protocol.md`: document `voice_members` field on voice channel entries in `channel_list` and note the rebroadcast-on-voice-change behaviour
- [x] 10.4 Update `docs/protocol.md`: add `user_online` and `user_offline` to the "All S2C message types" list
