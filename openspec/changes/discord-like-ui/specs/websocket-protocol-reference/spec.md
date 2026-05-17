## ADDED Requirements

### Requirement: user_online S2C message documented
`docs/protocol.md` SHALL document the `user_online` S2C message type with its field schema and the condition that triggers it.

#### Scenario: user_online entry present in S2C section
- **WHEN** a developer reads the S2C section of `docs/protocol.md`
- **THEN** they SHALL find a `user_online` entry with fields: `type` (string, `"user_online"`), `username` (string, the newly connected user's name)
- **THEN** the entry SHALL state that this message is broadcast to all connected clients except the authenticating client itself

### Requirement: user_offline S2C message documented
`docs/protocol.md` SHALL document the `user_offline` S2C message type with its field schema and the condition that triggers it.

#### Scenario: user_offline entry present in S2C section
- **WHEN** a developer reads the S2C section of `docs/protocol.md`
- **THEN** they SHALL find a `user_offline` entry with fields: `type` (string, `"user_offline"`), `username` (string, the disconnected user's name)
- **THEN** the entry SHALL state that this message is broadcast on both clean and abnormal client disconnection

### Requirement: auth_ok documents online_users and known_users fields
`docs/protocol.md` SHALL document the `online_users` and `known_users` fields added to the `auth_ok` S2C response.

#### Scenario: online_users and known_users present in auth_ok field table
- **WHEN** a developer reads the `auth_ok` S2C entry in `docs/protocol.md`
- **THEN** they SHALL find rows for `online_users` (array of strings, usernames of all currently connected clients) and `known_users` (array of strings, all registered usernames; equals `online_users` when auth is disabled)

### Requirement: channel_list documents voice_members field
`docs/protocol.md` SHALL document the `voice_members` field added to voice channel objects in the `channel_list` S2C response, and note that a `channel_list` is re-broadcast to all clients on any voice state change.

#### Scenario: voice_members field present in channel_list documentation
- **WHEN** a developer reads the `channel_list` S2C entry in `docs/protocol.md`
- **THEN** they SHALL find a note that voice channel objects include a `voice_members` array (list of usernames currently in that channel)
- **THEN** they SHALL find a note that `channel_list` is re-broadcast to all connected clients whenever voice membership changes

## MODIFIED Requirements

### Requirement: All C2S message types are documented
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all C2S types including: auth, join, leave, message, nick, create, list_channels, ping, voice_join, voice_leave, voice_offer, voice_answer, voice_ice, change_password

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all S2C types including: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, user_list, error, pong, voice_state, voice_offer, voice_answer, voice_ice, password_changed, password_change_error, user_online, user_offline
