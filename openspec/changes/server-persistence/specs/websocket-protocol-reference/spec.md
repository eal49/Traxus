## ADDED Requirements

### Requirement: C2S delete_channel documented
`docs/protocol.md` SHALL include a `delete_channel` subsection in the Client → Server section with field table and description.

#### Scenario: delete_channel entry present
- **WHEN** a developer reads the C2S section of `docs/protocol.md`
- **THEN** they SHALL find `delete_channel` with fields: `type` (required, `"delete_channel"`), `channel` (required, channel name without `#`)
- **THEN** the entry SHALL note that the default channels `general`, `random`, and `dev` cannot be deleted

### Requirement: S2C channel_deleted documented
`docs/protocol.md` SHALL include a `channel_deleted` subsection in the Server → Client section with field table and delivery context.

#### Scenario: channel_deleted entry present
- **WHEN** a developer reads the S2C section of `docs/protocol.md`
- **THEN** they SHALL find `channel_deleted` with fields: `type` (string, `"channel_deleted"`), `channel` (string, the deleted channel name)
- **THEN** the entry SHALL note that this message is broadcast to all connected clients and that clients currently viewing the deleted channel should switch to `#general`

### Requirement: Error code cannot_delete_default_channel documented
`docs/protocol.md` error codes table SHALL include `cannot_delete_default_channel` with trigger condition.

#### Scenario: Error code listed
- **WHEN** a developer reads the error codes table in `docs/protocol.md`
- **THEN** they SHALL find `cannot_delete_default_channel` with trigger: "delete_channel targeting general, random, or dev"

## MODIFIED Requirements

### Requirement: All C2S message types are documented
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all C2S types including: auth, join, leave, message, nick, create, delete_channel, list_channels, ping, voice_join, voice_leave, voice_offer, voice_answer, voice_ice, change_password

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all S2C types including: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, channel_deleted, user_list, error, pong, voice_state, voice_offer, voice_answer, voice_ice, password_changed, password_change_error
