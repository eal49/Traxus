## ADDED Requirements

### Requirement: change_password C2S message is documented
`docs/protocol.md` SHALL document the `change_password` C2S message type.

#### Scenario: change_password entry present
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find an entry for `change_password` with fields: `type` (string, required), `old_password` (string, required), `new_password` (string, required)

### Requirement: password_changed and password_change_error S2C messages are documented
`docs/protocol.md` SHALL document both S2C responses to a `change_password` request.

#### Scenario: password_changed entry present
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find an entry for `password_changed` with field: `type` (string)

#### Scenario: password_change_error entry present
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find an entry for `password_change_error` with fields: `type` (string), `reason` (string — one of `wrong_password`, `too_short`, `same_password`, `auth_disabled`)

## MODIFIED Requirements

### Requirement: All C2S message types are documented
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all C2S types including: auth, join, leave, message, nick, create, list_channels, ping, voice_join, voice_leave, voice_offer, voice_answer, voice_ice, change_password

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all S2C types including: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, user_list, error, pong, voice_state, voice_offer, voice_answer, voice_ice, password_changed, password_change_error
