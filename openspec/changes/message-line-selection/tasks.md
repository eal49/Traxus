## 1. Protocol — msg_id and pin message types

- [x] 1.1 Add `C2S.PIN_MESSAGE` and `C2S.UNPIN_MESSAGE` constants to `shared/message_types.py`
- [x] 1.2 Add `S2C.PIN_ADDED` constant to `shared/message_types.py`

## 2. Server — msg_id generation and pin storage

- [x] 2.1 In `ChannelRegistry`, add `_pins: dict[str, dict]` (channel → pin payload) and methods `set_pin(channel, payload)`, `get_pin(channel) -> dict | None`
- [x] 2.2 In `ChannelRegistry`, include current pin payload in the join response data returned by `get_channel_data()` (or equivalent join helper)
- [x] 2.3 In `MessageRouter._handle_message`, generate `msg_id = str(uuid4())`, attach it to the outgoing S2C payload before broadcasting, and cache the message content for pin lookups
- [x] 2.4 In `MessageRouter`, add handler for `C2S.PIN_MESSAGE`: validate channel membership, call `ChannelRegistry.set_pin`, broadcast `S2C.PIN_ADDED` with `{msg_id, username, content, channel}` to all channel members

## 3. Client — MessageView augmentation

- [x] 3.1 Add `_payloads: list[dict | None]` to `MessageView.__init__`; append payload alongside each markup line in `add_chat()`; append `None` for system/local messages
- [x] 3.2 Add `_cursor: int | None` to `MessageView`; add `enter_selection_mode()` / `exit_selection_mode()` methods that set/clear `_cursor` and trigger a full redraw
- [x] 3.3 Implement `_redraw()` in `MessageView`: `clear()` then re-render all `_lines`, wrapping the cursor line with a reverse-video highlight (e.g. `[reverse]...[/reverse]`)
- [x] 3.4 Add `move_cursor(delta: int)` to `MessageView`: clamps cursor within `[0, len(_lines)-1]`, calls `_redraw()`
- [x] 3.5 Add `selected_payload() -> dict | None` to `MessageView`: returns `_payloads[_cursor]` when cursor is active

## 4. Client — InputBar selection mode detection

- [x] 4.1 In `InputBar`, watch `Input.Changed` events; when value matches `^/(quote|pin)\s$`, post a `SelectionModeRequested(command: str)` message to the app and clear the input value
- [x] 4.2 Add `disable()` / `enable()` helpers to `InputBar` that set the underlying `Input.disabled` and update visual state

## 5. Client — App wiring for selection mode

- [x] 5.1 In `TraxusApp`, handle `SelectionModeRequested`: record pending command (`"quote"` or `"pin"`), call `MessageView.enter_selection_mode()`, call `InputBar.disable()`
- [x] 5.2 In `TraxusApp`, intercept Up/Down key events when selection mode is active (priority binding) and call `MessageView.move_cursor(-1)` / `move_cursor(+1)`
- [x] 5.3 In `TraxusApp`, intercept Enter when selection mode is active: call `MessageView.selected_payload()`, dispatch to `_handle_quote()` or `_handle_pin()`, then call `MessageView.exit_selection_mode()` and `InputBar.enable()`
- [x] 5.4 In `TraxusApp`, intercept Escape when selection mode is active: call `MessageView.exit_selection_mode()`, call `InputBar.enable()`, restore focus to InputBar

## 6. Client — /quote action

- [x] 6.1 Implement `_handle_quote(payload: dict | None, line_markup: str)` in `TraxusApp`: if `payload` is not None use `f"> @{payload['username']}: {payload['content']}"`, otherwise strip markup from `line_markup` and use `f"> {plain_text}"`; set `InputBar.value` to the result and focus it
- [x] 6.2 Add `"quote"` to `KNOWN_COMMANDS` in `client/commands.py` with help text `"/quote  — quote a line from the message history"`

## 7. Client — /pin action and pin header

- [x] 7.1 Implement `_handle_pin(payload: dict | None)` in `TraxusApp`: if `payload` is None or has no `msg_id`, display local error; otherwise send `{type: C2S.PIN_MESSAGE, channel, msg_id}` via `WsWorker`
- [x] 7.2 Add `"pin"` to `KNOWN_COMMANDS` in `client/commands.py` with help text `"/pin  — pin a message to the top of the channel"`
- [x] 7.3 Add `#pin-header` `Static` widget to `ChatScreen.compose()`, above `MessageView`, hidden by default (`display: none`)
- [x] 7.4 Add `update_pin(payload: dict | None)` to `ChatScreen`: if payload is not None render `📌 @{username}: {content}` into `#pin-header` and show it; if None hide it
- [x] 7.5 In `TraxusApp.on_traxus_app_server_message`, handle `S2C.PIN_ADDED`: call `ChatScreen.update_pin(payload)`
- [x] 7.6 In `ChatScreen`, when joining a channel include pin data from the join response and call `update_pin` accordingly

## 8. Tests

- [x] 8.1 `tests/test_message_view.py`: test `_payloads` length matches `_lines`; test cursor highlight appears in redraw output; test `selected_payload()` returns correct entry
- [x] 8.2 `tests/test_message_view.py`: test `move_cursor` clamping at 0 and last line
- [x] 8.3 `tests/test_commands.py`: verify `"quote"` and `"pin"` are in `KNOWN_COMMANDS`
- [x] 8.4 `tests/test_message_router.py`: test that `_handle_message` attaches `msg_id` to outgoing payload; test `pin_message` handler broadcasts `S2C.PIN_ADDED` with correct fields
- [x] 8.5 `tests/test_channel_registry.py`: test `set_pin` / `get_pin`; test that `get_pin` returns None when no pin set; test that joining a pinned channel includes pin in response
- [x] 8.6 `tests/test_pin_e2e.py` (integration): `/pin ` activates selection mode; Enter on a pinned line sends correct server payload; pin header appears after `pin_added` broadcast
