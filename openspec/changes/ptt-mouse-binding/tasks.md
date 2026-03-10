## 1. PttKeyScreen Mouse Capture

- [x] 1.1 Add `on_mouse_down(self, event: events.MouseDown)` to `PttKeyScreen` in `client/screens/settings_screen.py`; call `event.stop()` and `self.dismiss(f"mouse{event.button}")`
- [x] 1.2 Update the `PttKeyScreen` prompt label from `"Press any key — Escape to cancel"` to `"Press any key or click a mouse button — Escape to cancel"`

## 2. TraxusApp Mouse PTT Handler

- [x] 2.1 Add `on_mouse_down(self, event: events.MouseDown)` to `TraxusApp` in `client/app.py`; when `self._ptt_key.startswith("mouse")` and `event.button == int(self._ptt_key[5:])`, call `event.stop()` and `self.toggle_ptt()`; guard the `int()` parse in a `try/except ValueError`

## 3. Documentation

- [x] 3.1 Update the PTT line in `HELP_TEXT` in `client/commands.py` to note that a mouse button can also be used as the PTT binding
- [x] 3.2 Update `docs/commands.md` — PTT section and `/settings` section — to mention mouse button binding and note the left-click conflict warning

## 4. Tests

- [x] 4.1 Add `tests/test_ptt_mouse.py` with `unittest.IsolatedAsyncioTestCase` tests: mouse button press toggles PTT when `_ptt_key = "mouse3"`; non-matching button does not toggle; keyboard key still works when `_ptt_key = "f9"` (regression)
- [x] 4.2 Add a test that `PttKeyScreen` dismisses with `"mouse3"` when a mouse down event with `button=3` is simulated on the screen
- [x] 4.3 Run the full test suite; fix any failures
