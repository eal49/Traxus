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

---

### Requirement: Binary frame transport documented
`docs/protocol.md` Transport & Encoding section SHALL note that binary frames are used for audio data alongside text JSON frames.

#### Scenario: Transport section covers binary frames
- **WHEN** a developer reads the Transport & Encoding table in docs/protocol.md
- **THEN** they find a row stating binary frames carry raw PCM audio and the frame format (length-prefixed channel + optional username header + int16 LE samples)

---

### Requirement: C2S voice_join documented
`docs/protocol.md` SHALL include a `voice_join` subsection in the Client → Server section with field table and description.

#### Scenario: voice_join entry present
- **WHEN** a developer reads the C2S section
- **THEN** they find voice_join with fields: `type` (required, `"voice_join"`), `channel` (required, target voice channel name)

---

### Requirement: C2S voice_leave documented
`docs/protocol.md` SHALL include a `voice_leave` subsection in the Client → Server section.

#### Scenario: voice_leave entry present
- **WHEN** a developer reads the C2S section
- **THEN** they find voice_leave with fields: `type` (required, `"voice_leave"`), `channel` (required)

---

### Requirement: S2C voice_state documented
`docs/protocol.md` SHALL include a `voice_state` subsection in the Server → Client section with field table showing `type`, `channel`, and `users` array.

#### Scenario: voice_state entry present
- **WHEN** a developer reads the S2C section
- **THEN** they find voice_state with fields: `type`, `channel`, `users` (array of `{ user_id, username }`)

---

### Requirement: Error code not_a_voice_channel documented
`docs/protocol.md` error codes table SHALL include `not_a_voice_channel` with trigger condition.

#### Scenario: Error code listed
- **WHEN** a developer reads the error codes table
- **THEN** they find `not_a_voice_channel` listed with trigger: "voice_join targeting a text channel"

---

### Requirement: Client handling of user_list documented
`docs/protocol.md` SHALL document that the client uses the `user_list` S2C message to populate the member panel, not just acknowledge it.

#### Scenario: user_list client handling noted
- **WHEN** a developer reads the `user_list` entry in `docs/protocol.md`
- **THEN** they SHALL find a note stating the client uses the `users` array to populate the right-side member panel for the specified channel
