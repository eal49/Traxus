## 1. Status Bar Fix

- [x] 1.1 Fix status bar CSS: change `height: 1` to `height: 2` in `client/app.tcss`
- [x] 1.2 Add `_voice_channel: str` field to `StatusBar` and update `_build_markup()` to append `🔊 <channel>` when non-empty
- [x] 1.3 Add `update_voice_channel(name: str)` method to `StatusBar`
- [x] 1.4 Wire `on_watch_current_voice_channel()` reactive watcher in `TraxusApp` to call `chat.update_voice_channel()`

## 2. Login Persistence

- [x] 2.1 Add `last_server` and `last_username` keys (empty string defaults) to `DEFAULT_SETTINGS` in `client/settings.py`
- [x] 2.2 Update `LoginScreen.on_mount()` to read settings and pre-fill `#server-input` and `#nick-input`
- [x] 2.3 Update `LoginScreen._try_connect()` to call `save_settings()` with `last_server` and `last_username` after passing validation (before delegating to app)

## 3. Channel Sidebar Grouping

- [x] 3.1 Update `ChannelSidebar.refresh_channels()` to sort channels by type and insert non-interactive `ListItem` section headers (TEXT / VOICE) between groups
- [x] 3.2 Ensure `on_list_view_selected` ignores header items (items with `name=None` or a sentinel value)

## 4. Member Panel Sections

- [x] 4.1 Update `MemberPanel._build_markup()` to render a "Members" section header followed by text-channel members, and an "In Voice" section (with `🔊` prefix per user) only when `_voice_users` is non-empty
- [x] 4.2 Add a visual separator (blank line or dim rule) between the two sections when both are present
- [x] 4.3 Remove the old inline `🎤` prefix logic

## 5. Per-User Nick Colors

- [x] 5.1 Add a palette of 8 colors and a `nick_color(username)` helper (using `hashlib.md5`) in `client/widgets/message_view.py`
- [x] 5.2 Update `MessageView.add_chat()` to accept `self_username` and apply per-user palette color (own nick gets `[bold white]`)
- [x] 5.3 Update `ChatScreen.add_chat()` / callers in `TraxusApp` to pass `self.username` when calling `add_chat()`

## 6. Tests

- [x] 6.1 Run full test suite and fix any failures introduced by the above changes
