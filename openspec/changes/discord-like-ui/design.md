## Context

Traxus has a three-panel layout: channel sidebar (left), message view (centre), member panel (right). The member panel currently shows only the members of the active text channel plus an "In Voice" sub-section with per-user volume bars. The channel sidebar shows channel names only — no presence information.

The server has no global presence mechanism. Clients receive a `user_list` only for their current channel and `voice_state` only for the voice channel they have joined. There is no broadcast when a user connects or disconnects server-wide, and `channel_list` carries no membership data.

## Goals / Non-Goals

**Goals:**
- Right panel shows every user known to the server, split into Online / Offline sections
- Voice-active users in the right panel display an inline volume indicator (icon + %)
- Left sidebar voice channels show an indented list of current occupants
- Server emits `user_online` / `user_offline` to all connected clients on connect/disconnect
- `auth_ok` includes `online_users` snapshot + `known_users` (registered users from auth store when auth is enabled, same as `online_users` when auth is disabled)
- `channel_list` includes `voice_members` per voice channel and is re-broadcast to all clients on any voice join/leave

**Non-Goals:**
- Per-channel text membership in the sidebar (requires per-channel tracking not worth the complexity for text channels)
- Presence status beyond online/offline (no "idle", "do not disturb")
- User avatars or role badges
- Click/context-menu interaction on member rows (volume stays keyboard-only)

## Decisions

### D1 — Re-broadcast full `channel_list` on voice state change, not a delta event

**Decision:** When any client joins or leaves a voice channel, the server re-broadcasts the full `channel_list` (now including `voice_members` per channel) to every connected client.

**Alternatives considered:**
- New `S2C.VOICE_CHANNEL_UPDATE` delta event per channel — adds a new message type on server and client, complicates sidebar state management (must merge deltas), for negligible bandwidth saving at Traxus scale.
- Piggyback on existing `voice_state` but broadcast it to everyone — `voice_state` is keyed to a single channel and implies the recipient is in that channel; routing it to non-members would require new client-side logic to disambiguate.

**Rationale:** Full `channel_list` rebroadcast reuses existing codepaths. The payload is tiny (JSON array of channel objects). At the expected scale (< 50 users) this is never a bottleneck.

### D2 — `known_users` falls back to `online_users` when auth is disabled

**Decision:** When the server runs without auth (`TRAXUS_USERS` not set), `known_users` in `auth_ok` equals `online_users`. The client renders no Offline section in that mode (empty list).

**Alternatives considered:**
- Always send separate `known_users` even without auth — no persistent store to read from, so the list would always equal `online_users`, misleading the client into showing an empty Offline section permanently.

**Rationale:** Clean semantics: Offline means "registered but not here right now". Without a user store there are no registered-but-absent users.

### D3 — Volume indicator is a read-only display; keyboard UX unchanged

**Decision:** The right panel renders `🔇/🔈/🔉/🔊 N%` inline next to each voice user's name. ↑/↓ navigates among voice users; ←/→ adjusts volume. No click handler.

**Tiers:** `🔇` = 0 %, `🔈` = 1–50 %, `🔉` = 51–149 %, `🔊` = 150–200 %.

**Alternatives considered:**
- Click to cycle through presets — requires mouse event handling in Textual; inconsistent with the rest of the TUI interaction model.
- Inline slider on click — more complex, no clear benefit in a terminal context.

**Rationale:** Preserves the proven keyboard UX from `MemberPanel`. Adding a purely visual display layer on top of the existing volume logic is minimal-risk.

### D4 — `MemberPanel` widget is rewritten in-place, not renamed

**Decision:** `client/widgets/member_panel.py` is updated to implement the new server-wide roster. The widget ID `#members` and the `ChatScreen` API (`update_members`, `update_member_voice`) are kept where possible to minimise diff in `chat_screen.py` and `app.py`.

**Rationale:** No external code outside the client package references `MemberPanel` directly. Renaming the file would require updating imports without real benefit.

### D5 — `ChannelSidebar` stores voice membership received from `channel_list`

**Decision:** `ChannelSidebar.refresh_channels(channels)` reads the `voice_members` field from each voice channel dict and stores it. No separate `update_voice_members()` call needed; the sidebar self-manages this data.

**Rationale:** `channel_list` is already the single source of truth for channel metadata. Keeping voice membership inside that same dict avoids a second update path.

## Risks / Trade-offs

- **Stale Offline list when auth store changes at runtime** — if an admin adds a user to `users.json` while the server is running, existing clients won't see the new "known" user until they reconnect. Mitigation: acceptable for v1; a future `known_users_updated` broadcast can address this.
- **`channel_list` rebroadcast on every voice change** — if many clients join/leave voice in rapid succession the server sends multiple full channel_list payloads. Mitigation: payload is small; no debouncing needed at current scale. Add debounce if benchmarks show pressure.
- **Right panel width** — icon + "%" + number adds ~8 characters to voice user rows. Mitigation: existing `_MIN_WIDTH` / `_MAX_WIDTH` clamps already handle this; verify the max-width constant is sufficient (current `_MAX_WIDTH = 40`).
- **Offline section visibility when auth is disabled** — new users connecting to a no-auth server will see no Offline section, which could be confusing if they expect it. Mitigation: document in help text; section is simply absent rather than empty.

## Migration Plan

1. Deploy updated server (new message types, updated `auth_ok` + `channel_list` schema).
2. Old clients connecting to new server: they ignore unknown fields (`online_users`, `known_users`, `voice_members`) — no breakage.
3. New clients connecting to old server: `online_users` / `known_users` absent in `auth_ok` → right panel shows empty roster. `voice_members` absent in `channel_list` → sidebar shows no nested members. Graceful degradation.
4. No database migration; no persistent state changes.
