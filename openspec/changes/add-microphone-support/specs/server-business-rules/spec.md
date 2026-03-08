## ADDED Requirements

### Requirement: Voice channel type validation on voice_join
The server SHALL reject `voice_join` with `error { code: "not_a_voice_channel" }` if the target channel exists but is of type `"text"`.

#### Scenario: Text channel rejects voice_join
- **WHEN** a client sends `voice_join { channel: "general" }`
- **THEN** the server responds with `error { code: "not_a_voice_channel" }`

#### Scenario: Non-existent channel rejects voice_join
- **WHEN** a client sends `voice_join { channel: "missing" }` and no such channel exists
- **THEN** the server responds with `error { code: "no_such_channel" }`

---

### Requirement: Voice membership in broadcast scope table
`docs/server-rules.md` broadcast scope table SHALL include voice-scoped events.

#### Scenario: voice_state scope documented
- **WHEN** a developer reads the broadcast scope section
- **THEN** they find `voice_state` listed as channel-scoped (sent to voice members of the affected channel only)

#### Scenario: binary audio frame scope documented
- **WHEN** a developer reads the broadcast scope section
- **THEN** they find binary audio frames listed as channel-scoped, excluding the sender

---

### Requirement: Voice disconnect cleanup
When a client disconnects, the server SHALL remove them from all voice channels and the disconnect sequence documentation SHALL reflect this.

#### Scenario: Disconnect cleanup removes voice membership
- **WHEN** a client's WebSocket closes
- **THEN** the client is removed from every voice channel they were in (in addition to text channels)

#### Scenario: No voice_state sent on disconnect
- **WHEN** a client disconnects from a voice channel
- **THEN** the server does NOT send a `voice_state` update (the remaining members will detect the absence via any future state refresh — this is a known limitation)
