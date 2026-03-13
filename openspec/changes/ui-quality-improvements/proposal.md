## Why

The Traxus TUI has several small but visible rough edges: the status bar displays no text at all (a CSS height bug renders only a colored strip), the login screen forgets the server URL and username on every launch, the channel sidebar mixes text and voice channels without visual grouping, the member panel is a flat list that conflates text-channel and voice-channel presence, and all usernames are rendered in the same green color making busy conversations harder to scan. These are quick, independent wins that collectively make daily use significantly more pleasant.

## What Changes

- **Login screen**: pre-fill the server URL and username fields from `~/.config/traxus/settings.json` on launch; save them back when the user connects successfully. No auto-connect — the user still presses Connect.
- **Status bar bug fix**: correct the CSS so the status bar actually shows its text content (`height: 1` + `border-top: tall` collapses content to zero lines).
- **Status bar — active voice channel**: when the user is in a voice channel, show `🔊 <channel>` in the status bar between the nick and the PTT indicator.
- **Channel sidebar grouping**: render two labeled sections — TEXT and VOICE — instead of a flat mixed list. Visual grouping only; inline voice member counts (requires server changes) are a future TODO.
- **Member panel sections**: split the panel into two named sections — "Members" (text-channel presence) and "In Voice" (voice-channel presence). Cleaner than the current flat list with mixed 🎤 markers. "Currently speaking" indicators (requires server changes) are a future TODO.
- **Per-user nick colors**: hash each username to a consistent color from a small curated palette. The current user's own nick is rendered in white/bold to stand out. All other users get a stable color across sessions.

## Capabilities

### New Capabilities

- `login-persistence`: Login screen pre-fills server URL and username from saved settings and persists them on successful connect.

### Modified Capabilities

- `settings-command`: Settings file gains two new keys (`last_server`, `last_username`).
- `member-list-panel`: Panel splits into two sections (text members / voice members) instead of a flat list.

## Impact

- `client/settings.py` — two new settings keys
- `client/screens/login_screen.py` — read settings on mount, write on connect
- `client/app.tcss` — status bar height fix; channel sidebar section headers
- `client/widgets/status_bar.py` — add voice channel segment to markup
- `client/app.py` — pass `current_voice_channel` into status bar updates
- `client/widgets/channel_sidebar.py` — split render into TEXT / VOICE sections
- `client/widgets/member_panel.py` — split render into Members / In Voice sections
- `client/widgets/message_view.py` — `add_chat()` uses per-user color instead of hardcoded green
- No server changes. No new dependencies.
