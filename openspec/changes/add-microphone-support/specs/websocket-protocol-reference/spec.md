## ADDED Requirements

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
