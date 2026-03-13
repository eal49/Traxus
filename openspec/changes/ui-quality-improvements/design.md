## Context

Six independent UI rough edges are addressed in one batch: a status bar height CSS bug (text invisible), missing login field persistence, flat channel sidebar (text and voice mixed), flat member panel (text presence and voice presence merged), hardcoded username color, and missing voice-channel indicator in the status bar. All changes are confined to the client; no server or protocol changes are required. Each sub-change is small and self-contained.

## Goals / Non-Goals

**Goals:**
- Fix the status bar so its text content is visible
- Pre-fill login screen from saved settings
- Group sidebar channels into TEXT / VOICE sections
- Split member panel into Members / In Voice sections
- Assign consistent per-user nick colors from a palette
- Show active voice channel name in the status bar

**Non-Goals:**
- Inline voice member counts in the sidebar (requires server changes — future TODO)
- "Currently speaking" indicator in the member panel (requires per-frame speaker tagging — future TODO)
- Auto-connect on launch
- Dark/light theme switching
- Any server-side changes

## Decisions

### D1: Status bar height — change to `height: 2` rather than removing the border

**Chosen:** `height: 2`
**Alternatives:**
- Remove `border-top: tall` — saves a line but loses the visual separator between InputBar and StatusBar. The two panels have similar background colors (`$surface` vs `$surface-darken-1`) so the border provides a useful hard edge.
- `border-top: solid` — not a Textual-valid value; `tall` is the standard 1-char-height border type.

Setting `height: 2` gives one row to the border and one row to the `Static` content.

### D2: Login persistence — extend existing `settings.json`, no new file

Settings already has `~/.config/traxus/settings.json` with graceful-fallback load. Adding `last_server: ""` and `last_username: ""` keys costs nothing. `LoginScreen.on_mount()` reads settings and pre-fills both `Input` widgets. On successful connect, `LoginScreen._try_connect()` writes them back via `save_settings()`.

### D3: Sidebar sections — static section headers rendered inline, not separate widgets

The current sidebar uses a single `ListView`. Two approaches:

- **Option A:** Replace `ListView` with a `ScrollableContainer` and two `Static` section headers + two `ListView`s.
- **Option B (chosen):** Keep one `ListView`, insert non-interactive `ListItem` header rows (styled differently, not selectable) between text and voice channels.

Option B requires less structural change and the existing `refresh_channels()` method just needs to sort channels by type and insert header items. Header items have `name=None` so the `on_list_view_selected` handler naturally ignores them.

### D4: Per-user nick colors — hash in `message_view.py`, palette of 8

A 8-color palette of distinct hues that all read well on the dark background. `hash(username) % 8` gives a stable index. The palette excludes red (`#ed4245`, used for errors) and the accent green (`#57f287`, used for system messages and the own-nick fallback).

Own username is identified by passing `self_username` into `add_chat()`. When `payload["username"] == self_username`, render with `[bold white]` instead of the palette color.

`TraxusApp` already holds `self.username` as a reactive. `ChatScreen.add_chat()` will receive the username from the app.

**Alternative considered:** compute colors server-side (not worth the complexity; purely cosmetic).

### D5: Member panel sections — two `Static` blocks with `update()` calls, no separate widgets

`MemberPanel` currently extends `Static` and rebuilds its entire content on every `set_members()` / `update_voice()` call. That approach scales fine here — just render two labeled sections in `_build_markup()`:

```
Members ────────────
alice
charlie

In Voice ───────────
🔊 bob
```

If `_voice_users` is empty, the "In Voice" section is omitted.

### D6: Status bar voice channel — new `_voice_channel` field on StatusBar, updated from app

`StatusBar` gains a `_voice_channel: str` field. `update_voice_channel(name: str)` sets it and calls `_refresh_content()`. The markup builder appends `🔊 <name>` when `_voice_channel` is non-empty, between the nick and the PTT indicator.

`TraxusApp.on_watch_current_voice_channel()` (a Textual reactive watcher) calls `chat.update_voice_channel()` whenever `current_voice_channel` changes. This is cleaner than scattering the update call across every voice join/leave handler.

## Risks / Trade-offs

- [Sidebar section headers as ListItems] Header rows appear in the keyboard-navigable list — pressing Enter on one does nothing (correct) but focus moves to them (minor UX oddity). Mitigation: style them visually distinct and non-interactive.
- [Login pre-fill] If the saved server URL is stale (server moved), the user sees a connection error on first attempt. Mitigation: fields are editable; error message is already displayed.
- [Username color consistency] `hash()` in Python is randomized per-process by default (PYTHONHASHSEED). Use `hashlib.md5(username.encode()).hexdigest()` to get a stable cross-session hash.

## Migration Plan

No migration needed. Settings file gains new optional keys — existing settings files without them fall back to empty strings (no pre-fill, same as current behavior).
