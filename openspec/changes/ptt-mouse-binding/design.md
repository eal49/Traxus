## Context

PTT is currently toggled by a configurable keyboard key (`self._ptt_key`, defaulting to `"f9"`), handled in `TraxusApp.on_key`. The settings screen (`PttKeyScreen`) captures the first keypress and dismisses with its string. Mouse buttons are a common choice for PTT in voice applications — side buttons (mouse4/mouse5) or middle click (mouse3) can be pressed without moving the hand off the mouse.

Textual propagates mouse events (`events.MouseDown`) through the widget hierarchy just like key events. The App receives them during the bubbling phase. The `PttKeyScreen` modal, being the active screen, intercepts mouse events directed at its area before any underlying widget.

## Goals / Non-Goals

**Goals:**
- `/settings` → PTT Key capture screen accepts mouse button presses in addition to keyboard keys
- Mouse buttons stored as `"mouse1"` … `"mouse5"` strings verbatim in `settings.json`
- `TraxusApp.on_mouse_down` toggles PTT when the configured button matches
- Capture screen prompt updated to mention both input types
- Works with any mouse button Textual can represent (button numbers 1–5)

**Non-Goals:**
- Mouse scroll wheel (scroll is not a button press in Textual)
- Distinguishing between mouse down and mouse up for hold-to-talk (PTT remains toggle mode)
- Any special handling for button 1 conflicts — left click is allowed as a binding but the user accepts the interaction consequences
- Modifier+mouse combinations (e.g., ctrl+click)

## Decisions

**Naming scheme: `"mouseN"` string**

Mouse buttons are stored as `"mouse1"`, `"mouse2"`, `"mouse3"`, `"mouse4"`, `"mouse5"`. The App-level PTT handler already does exact-string comparison (`event.key == self._ptt_key`). For mouse, we add a parallel `on_mouse_down` that parses `event.button` and compares to the suffix of `self._ptt_key`.

```python
def on_mouse_down(self, event: events.MouseDown) -> None:
    if self._ptt_key.startswith("mouse"):
        try:
            if event.button == int(self._ptt_key[5:]):
                event.stop()
                self.toggle_ptt()
        except ValueError:
            pass
```

Alternative considered: a dedicated enum or dataclass for the binding type. Rejected — the single-string scheme already works for all keyboard keys and is consistent with what is stored in `settings.json`. Adding structure for a two-branch union (key | mouse) adds complexity without benefit.

**PttKeyScreen captures both key and mouse events**

`PttKeyScreen` overrides both `on_key` and `on_mouse_down`. Either fires first; it calls `event.stop()` and dismisses with the appropriate string (`event.key` or `f"mouse{event.button}"`). Escape in `on_key` remains the cancel path; no mouse cancel path is defined (there is no "mouse Escape").

```python
def on_mouse_down(self, event: events.MouseDown) -> None:
    event.stop()
    self.dismiss(f"mouse{event.button}")
```

**Display name for mouse buttons**

The `PttKeyScreen` current-key label shows the raw string stored in settings (e.g., `"mouse3"`). No friendly label mapping is added — the raw string is unambiguous and avoids a lookup table that needs updating if Textual changes button numbering.

**No capture-phase override**

App-level `on_mouse_down` fires during the bubble phase (after widgets under the cursor have already processed the event). For mouse3/4/5 this is fine since Textual widgets don't handle those buttons. For mouse1 (left click), a UI widget may have already processed the event before PTT fires. This is documented as a known limitation and is consistent with the existing `on_key` behaviour — the user is responsible for choosing a non-conflicting button.

## Risks / Trade-offs

[Mouse button 1 conflict] Left click is also used for widget interaction (focus, list selection, buttons). If PTT is bound to mouse1, every left click also toggles PTT. → Mitigation: display a clear warning in the capture screen prompt. The user can rebind to any other key or button via `/settings` if they change their mind.

[Terminal mouse support] Some terminals or SSH sessions disable mouse events (`TERM=dumb`, no `MOUSE` capability). In this case `on_mouse_down` never fires. → Mitigation: defaults remain F9 (keyboard); the user must pick a mouse button themselves via `/settings`. If mouse events don't arrive, they can fall back to a keyboard key.

[Button 4/5 availability] Side buttons (mouse4/5) are forwarded by most modern terminal emulators (kitty, wezterm, alacritty) but not all (xterm, older gnome-terminal). → Mitigation: no action needed — if the button press is not forwarded, PTT simply does not fire and the user can reconfigure.

[Bubble phase timing] By the time `on_mouse_down` fires on the App, the widget under the cursor has already handled the event. `event.stop()` has no retroactive effect. → Mitigation: document the limitation; recommend mouse3/4/5 for PTT.
