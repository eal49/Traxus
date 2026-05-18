## ADDED Requirements

### Requirement: Any authenticated user can delete a channel
The server SHALL support a `delete_channel` C2S message. Any authenticated client MAY send it. The server SHALL delete the named channel, all its messages, and its pin from the database, then broadcast `channel_deleted` to all connected clients. The three default channels (`#general`, `#random`, `#dev`) SHALL NOT be deletable.

#### Scenario: Channel deleted successfully
- **WHEN** a client sends `delete_channel { channel: "old-topic" }` and `#old-topic` exists and is not a default channel
- **THEN** the server SHALL remove `#old-topic` from the database (cascading messages and pins), remove it from the in-memory registry, and broadcast `channel_deleted { channel: "old-topic" }` to all connected clients

#### Scenario: Default channels are protected
- **WHEN** a client sends `delete_channel { channel: "general" }`
- **THEN** the server SHALL respond with `error { code: "cannot_delete_default_channel" }` and take no further action

#### Scenario: Non-existent channel returns error
- **WHEN** a client sends `delete_channel { channel: "ghost" }` and `#ghost` does not exist
- **THEN** the server SHALL respond with `error { code: "no_such_channel" }`

### Requirement: Clients handle channel_deleted broadcast
When a client receives `channel_deleted`, it SHALL remove the channel from the channel sidebar. If the client is currently joined to the deleted channel, it SHALL switch to `#general` automatically.

#### Scenario: Deleted channel removed from sidebar
- **WHEN** the client receives `channel_deleted { channel: "old-topic" }`
- **THEN** `#old-topic` SHALL no longer appear in the channel sidebar

#### Scenario: Active channel deleted forces switch to general
- **WHEN** the client is viewing `#old-topic` and receives `channel_deleted { channel: "old-topic" }`
- **THEN** the client SHALL automatically join and switch to `#general`

### Requirement: channel_deleted is a new S2C message type
The server SHALL add `S2C.CHANNEL_DELETED = "channel_deleted"` to `shared/message_types.py`. The message SHALL carry the field `channel` (string — the deleted channel name). The server SHALL add `C2S.DELETE_CHANNEL = "delete_channel"` to `shared/message_types.py`.

#### Scenario: Constants exist in shared module
- **WHEN** `shared/message_types.py` is imported
- **THEN** `S2C.CHANNEL_DELETED` SHALL equal `"channel_deleted"` and `C2S.DELETE_CHANNEL` SHALL equal `"delete_channel"`

### Requirement: Cascade deletion removes messages and pins
The `messages` and `pins` tables SHALL use `REFERENCES channels(name) ON DELETE CASCADE`. Deleting a row from `channels` SHALL automatically delete all associated messages and pins.

#### Scenario: Messages and pin removed on channel deletion
- **WHEN** a channel with 30 messages and 1 pin is deleted
- **THEN** the `messages` and `pins` tables SHALL contain no rows for that channel after the deletion commits
