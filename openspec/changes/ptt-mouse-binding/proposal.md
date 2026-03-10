## Why

The PTT key capture currently only accepts keyboard keys. Users who prefer to bind PTT to a mouse button (e.g., a side button or middle click) cannot do so. Adding mouse button support to the `/settings` PTT binding screen makes PTT accessible to a wider range of hardware setups.

## What Changes

- `PttKeyScreen` captures mouse button presses in addition to keyboard keypresses — whichever comes first wins
- Mouse buttons are stored as the strings `"mouse1"` (left), `"mouse2"` (right), `"mouse3"` (middle/wheel), `"mouse4"`, `"mouse5"` (side buttons if supported)
- `TraxusApp` gains an `on_mouse_down` handler that calls `toggle_ptt()` when the configured button matches, mirroring the existing `on_key` handler
- `PttKeyScreen` prompt updated to say "Press any key or click a mouse button — Escape to cancel"
- `/help` and `docs/commands.md` note that PTT can be bound to a mouse button via `/settings`

**Note:** Binding PTT to mouse button 1 (left click) conflicts with normal TUI navigation and is strongly discouraged. Middle (mouse3) or side buttons (mouse4/5) are recommended.

## Capabilities

### New Capabilities

- `ptt-mouse-binding`: Extends PTT binding to accept mouse buttons captured in the settings key-capture screen, stored as `mouseN` strings, and toggled via an App-level mouse-down handler

### Modified Capabilities

- `settings-command`: PTT capture screen now also listens for mouse button events; prompt text updated to reflect both input types

## Impact

- `client/screens/settings_screen.py` — `PttKeyScreen.on_mouse_down` added; prompt label updated
- `client/app.py` — new `on_mouse_down` handler checks `self._ptt_key` for `"mouseN"` prefix
- `client/commands.py` — HELP_TEXT PTT line updated to mention mouse button option
- `docs/commands.md` — PTT and `/settings` sections mention mouse button binding
- No server changes; no shared/ changes; no new dependencies
