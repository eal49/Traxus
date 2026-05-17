## Purpose
Document every C2S and S2C WebSocket message type used by Traxus, including field schemas, lifecycle, and transport details, in `docs/protocol.md`.
## Requirements
### Requirement: WebSocket protocol reference document exists
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all C2S types including: auth, join, leave, message, nick, create, list_channels, ping, voice_join, voice_leave, voice_offer, voice_answer, voice_ice

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all S2C types including: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, user_list, error, pong, voice_state, voice_offer, voice_answer, voice_ice

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

### Requirement: WebRTC signaling flow documented
`docs/protocol.md` SHALL include a WebRTC Signaling Flow section describing the offer/answer/ICE exchange sequence used to establish peer-to-peer audio.

#### Scenario: Signaling flow section present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find a section describing the three-message WebRTC signaling flow: voice_offer, voice_answer, voice_ice

---

### Requirement: voice_offer signaling message documented
`docs/protocol.md` SHALL document the `voice_offer` C2S and S2C message types with field schema and usage context.

#### Scenario: voice_offer C2S entry present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find a `voice_offer` C2S entry with fields: `type` (string), `to_user` (string), `sdp` (string, SDP offer body)
- **THEN** the entry SHALL state that the server relays this to the named peer in the same voice channel with `from_user` set

#### Scenario: voice_offer S2C entry present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find a `voice_offer` S2C entry with fields: `type`, `from_user`, `to_user`, `sdp`

---

### Requirement: voice_answer signaling message documented
`docs/protocol.md` SHALL document the `voice_answer` C2S and S2C message types.

#### Scenario: voice_answer entries present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find `voice_answer` C2S and S2C entries with the same field layout as `voice_offer`
- **THEN** the entry SHALL note this message carries the SDP answer from the callee to the caller

---

### Requirement: voice_ice signaling message documented
`docs/protocol.md` SHALL document the `voice_ice` C2S and S2C message types.

#### Scenario: voice_ice entries present
- **WHEN** a developer reads `docs/protocol.md`
- **THEN** they SHALL find `voice_ice` C2S and S2C entries with fields: `type`, `to_user` / `from_user`, `candidate` (string or null), `sdpMid` (string), `sdpMLineIndex` (integer)
- **THEN** the entry SHALL note that `candidate: null` signals end-of-candidates

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

---

### Requirement: auth C2S message documents optional password field
`docs/protocol.md` SHALL document that the `auth` C2S message accepts an optional `password` field (string). The field table SHALL mark `password` as optional with a description noting it is required only when the server has `TRAXUS_USERS` configured.

#### Scenario: password field present in auth field table
- **WHEN** a developer reads the `auth` C2S entry in `docs/protocol.md`
- **THEN** they SHALL find a row for `password` with type `string`, required `no`, and a description explaining it is only checked when the server runs with credentials configured

### Requirement: auth_error documents wrong_password reason
`docs/protocol.md` SHALL document `wrong_password` as a valid `reason` value in the `auth_error` S2C message, alongside existing reasons (`invalid_username`, `username_taken`).

#### Scenario: wrong_password reason listed
- **WHEN** a developer reads the `auth_error` S2C entry in `docs/protocol.md`
- **THEN** they SHALL find `wrong_password` in the reasons table with a description: "Password missing or incorrect; also returned for unknown usernames to prevent enumeration"

### Requirement: Connection lifecycle documents auth-mode behaviour
`docs/protocol.md` connection lifecycle section SHALL note that when the server is configured with `TRAXUS_USERS`, a `password` field is required in the `auth` message and a missing or incorrect password results in `auth_error { reason: "wrong_password" }` followed by connection close.

#### Scenario: Auth-mode behaviour in lifecycle section
- **WHEN** a developer reads the lifecycle section
- **THEN** they SHALL find a note that password verification applies only when `TRAXUS_USERS` is set on the server

### Requirement: All C2S message types are documented
The project SHALL contain `docs/protocol.md` documenting every C2S and S2C JSON message type with field schemas and usage context.

#### Scenario: All C2S message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all C2S types including: auth, join, leave, message, nick, create, list_channels, ping, voice_join, voice_leave, voice_offer, voice_answer, voice_ice, change_password

#### Scenario: All S2C message types are documented
- **WHEN** a developer opens `docs/protocol.md`
- **THEN** they SHALL find entries for all S2C types including: auth_ok, auth_error, channel_list, joined, left, chat, system, nick_changed, channel_created, user_list, error, pong, voice_state, voice_offer, voice_answer, voice_ice, password_changed, password_change_error

