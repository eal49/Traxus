## ADDED Requirements

### Requirement: WebSocket protocol reference document exists
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all eight C2S types: auth, join, leave, message, nick, create, list_channels, ping

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all eleven S2C types: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, user_list, error, pong

#### Scenario: Each message entry has a field schema table
- **WHEN** a developer reads any message type entry
- **THEN** the entry SHALL include a Markdown table with columns: Field, Type, Required, Description

### Requirement: Connection lifecycle is documented
The `docs/protocol.md` file SHALL include a connection lifecycle section describing the sequence from TCP connect to disconnect.

#### Scenario: Lifecycle sequence diagram present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find a text-based sequence diagram or numbered flow covering: TCP connect → auth → auth_ok → auto-join #general → normal operation → disconnect cleanup

#### Scenario: Auth-first rule is explicit
- **WHEN** a developer reads the lifecycle section
- **THEN** the document SHALL state that the server rejects all non-auth messages before authentication with error code `not_authenticated`

### Requirement: Transport and encoding documented
The `docs/protocol.md` file SHALL specify the transport layer, encoding, and message framing.

#### Scenario: Transport details present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** the document SHALL state: WebSocket over TCP, JSON-encoded UTF-8 text frames, one JSON object per frame, `type` field required on every message
