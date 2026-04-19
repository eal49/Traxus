# pin-command Specification

## Purpose
TBD - created by archiving change message-line-selection. Update Purpose after archive.
## Requirements
### Requirement: Every chat message carries a server-assigned msg_id
The server SHALL attach a unique `msg_id` string to every chat message it relays to channel members, so individual messages can be referenced across clients.

#### Scenario: Outgoing chat payload includes msg_id
- **WHEN** the server relays a `chat` message to a channel
- **THEN** the S2C payload SHALL include a `"msg_id"` key containing a non-empty string unique to that message

#### Scenario: msg_id is included in channel history
- **WHEN** a client joins a channel and receives message history
- **THEN** each historical message payload SHALL include its original `msg_id`

### Requirement: /pin command is registered
The client SHALL recognise `/pin` as a known slash command and include it in the help text.

#### Scenario: /pin appears in /help output
- **WHEN** the user runs `/help`
- **THEN** the output SHALL include an entry for `/pin` describing its purpose

### Requirement: /pin activates line selection and pins the selected message
After the user selects a message via the selection cursor, `/pin` SHALL send a pin request to the server. The server broadcasts the pin to all channel members. The message appears in a sticky header at the top of the channel view.

#### Scenario: Selecting a message with msg_id sends pin_message to server
- **WHEN** the user activates `/pin` selection mode and presses Enter on a chat line that has a `msg_id`
- **THEN** the client SHALL send `{"type": "pin_message", "channel": "<current_channel>", "msg_id": "<msg_id>"}` to the server

#### Scenario: Selecting a line without msg_id with /pin shows an error
- **WHEN** the user activates `/pin` selection mode and presses Enter on a line with no associated `msg_id` (system message or legacy message without ID)
- **THEN** the client SHALL display a local error message and NOT send any message to the server

#### Scenario: Server broadcasts pin_added to channel members
- **WHEN** the server receives a valid `pin_message` request for channel "#general" with `msg_id` "abc"
- **THEN** the server SHALL broadcast `{"type": "pin_added", "channel": "#general", "msg_id": "abc", "username": "<sender>", "content": "<message content>"}` to all members of "#general"

#### Scenario: Pinning a new message replaces the existing pin
- **WHEN** a pin already exists in the channel and the server receives a new `pin_message`
- **THEN** the server SHALL replace the existing pin with the new one
- **THEN** the server SHALL broadcast `{"type": "pin_added", ...}` with the new message details to all channel members

#### Scenario: Pin header is visible at top of channel view
- **WHEN** a `pin_added` message is received for the current channel
- **THEN** a sticky header SHALL appear above the message history displaying the pinned message in the format `📌 @nick: content`
- **THEN** the header SHALL remain visible regardless of the scroll position in the message history

#### Scenario: Pin header is absent when no pin is set
- **WHEN** no message is pinned in the current channel
- **THEN** the sticky pin header SHALL NOT be shown

#### Scenario: Late-joining clients receive the current pin
- **WHEN** a client joins a channel that has a pinned message
- **THEN** the server SHALL include the current pin payload in the join response
- **THEN** the client SHALL display the pin header immediately upon joining

### Requirement: Pinned message state is stored per channel in ChannelRegistry
The server SHALL maintain at most one pinned message per channel in memory.

#### Scenario: Pin is stored on server
- **WHEN** the server processes a `pin_message` request for channel "#general"
- **THEN** the channel's current pin SHALL be updated to the provided `msg_id` with its content cached

#### Scenario: Pin is cleared on server restart
- **WHEN** the server process restarts
- **THEN** all pins SHALL be cleared (in-memory only; no persistence required)

