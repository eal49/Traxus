## Why

Users cannot reference specific messages when chatting — there is no way to quote a previous line in context or highlight important messages for the channel. Adding keyboard-driven line selection with `/quote` and `/pin` commands closes this gap without leaving the keyboard.

## What Changes

- Every chat message sent by the server now carries a `msg_id` (UUID) so individual messages can be identified
- Typing `/quote ` or `/pin ` followed by a space activates a cursor in the message view; arrow keys move it; Enter selects the target line; Escape cancels
- `/quote` inserts IRC-style quoted text (`> @nick: content`) into the input bar, ready to send
- `/pin` sends a `pin_message` request to the server; the server broadcasts the pin to all channel members and the pinned message appears in a sticky header above the message list
- `/unpin` (or selecting an already-pinned message with `/pin`) removes the pin
- Pinned messages are stored in `ChannelRegistry` and sent to joining clients as part of the channel state

## Capabilities

### New Capabilities

- `message-line-selection`: Keyboard cursor in the message view, activated by `/quote ` or `/pin ` in the input bar; arrows navigate, Enter selects, Escape cancels
- `quote-command`: `/quote` slash command — selects a line via cursor and inserts `> @nick: content` into the input bar
- `pin-command`: `/pin` slash command — selects a line via cursor, sends `pin_message` to the server; pinned messages render in a sticky header at the top of the channel view; `/pin` on a pinned message unpins it

### Modified Capabilities

- `settings-command`: No requirement changes — unaffected
- `message-view`: The `MessageView` widget gains a parallel payload store and cursor rendering; existing display requirements are unchanged but internal structure changes

## Impact

- `shared/message_types.py`: New constants `C2S.PIN_MESSAGE`, `C2S.UNPIN_MESSAGE`, `S2C.PIN_ADDED`, `S2C.PIN_REMOVED`
- `server/channel_registry.py`: `_pins: dict[str, list[str]]` per channel; `msg_id` injected into chat payloads on send; pin CRUD methods
- `server/message_router.py`: Handlers for `pin_message` and `unpin_message`; `msg_id` attached to outgoing `S2C.MESSAGE` payloads
- `client/widgets/message_view.py`: `_payloads: list[dict|None]`, `_cursor: int|None`, cursor rendering via full redraw; pin header section
- `client/widgets/input_bar.py`: Detects `/quote ` and `/pin ` suffix to trigger selection mode; populates quoted text on selection
- `client/commands.py`: `quote` and `pin` added to `KNOWN_COMMANDS` and `HELP_TEXT`
- `client/app.py`: Handles `S2C.PIN_ADDED` / `S2C.PIN_REMOVED` server messages; routes to `ChatScreen`
- `client/screens/chat_screen.py`: Renders sticky pin header; passes `msg_id` through to `MessageView`
