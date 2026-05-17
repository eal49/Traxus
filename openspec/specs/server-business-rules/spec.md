## Purpose
Document the server-side validation rules, auth guard, and state invariants enforced by the Traxus server in `docs/server-rules.md`.

## Requirements

### Requirement: Server business rules reference document exists
The project SHALL contain `docs/server-rules.md` documenting the server-side validation constraints, auth guard, and state invariants enforced by the Traxus server.

#### Scenario: Auth guard rule is documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** they SHALL find the rule: every message type except `auth` requires a prior successful authentication; unauthenticated messages receive `error { code: "not_authenticated" }`

#### Scenario: Username validation rules documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: username must be 1–32 characters, no spaces, must be unique across connected clients; violations receive `auth_error` with reason `invalid_username` or `username_taken`

#### Scenario: Channel name validation rules documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: channel names must match `^[a-z0-9_-]{1,32}$`; violations receive `error { code: "invalid_channel_name" }`

#### Scenario: Nick change validation documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: new nick must be 1–32 characters with no spaces and not currently taken; violations receive `error { code: "nick_taken" }` or `error { code: "invalid_channel_name" }` (reuses validation code)

### Requirement: Broadcast scope rules are documented
The `docs/server-rules.md` file SHALL document which events are broadcast to whom.

#### Scenario: Channel-scoped broadcasts listed
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** they SHALL find a table or list showing: join/leave system messages and chat messages are broadcast only to members of the affected channel

#### Scenario: Global broadcasts listed
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: `nick_changed`, `channel_created`, and `channel_list` updates are broadcast to all connected clients

### Requirement: History and state invariants documented
The `docs/server-rules.md` file SHALL document the server's stateful guarantees.

#### Scenario: History cap documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: each channel retains the last 50 messages in memory; history is sent to clients on join

#### Scenario: Auto-join behaviour documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: upon successful auth, the server automatically joins the client to #general without requiring an explicit join message

#### Scenario: Disconnect cleanup documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: on disconnect, the server removes the client from all channel memberships, frees the username, and broadcasts a `system` disconnect notice to each channel the client was in

---

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

#### Scenario: Remaining voice members notified on disconnect
- **WHEN** a client disconnects from a voice channel
- **THEN** the server sends a `voice_state` update to remaining voice members of each channel the departing client was in

---

### Requirement: Auth guard documents credential verification mode
`docs/server-rules.md` SHALL document that when `TRAXUS_USERS` is set, the auth guard additionally requires a valid bcrypt password match. The rule SHALL state that an incorrect or missing password causes `auth_error { reason: "wrong_password" }` and connection close.

#### Scenario: Credential verification rule documented
- **WHEN** a developer reads `docs/server-rules.md` auth guard section
- **THEN** they SHALL find the rule: "When TRAXUS_USERS is configured, auth additionally checks bcrypt password; wrong or missing password → auth_error { reason: 'wrong_password' } and connection close"

### Requirement: No-auth fallback rule documented
`docs/server-rules.md` SHALL document that when `TRAXUS_USERS` is unset (or points to a missing file), the server operates in no-auth mode and accepts any valid username without a password.

#### Scenario: No-auth fallback rule documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** they SHALL find the rule: "When TRAXUS_USERS is unset or the credentials file is absent, password verification is skipped entirely (no-auth mode)"

### Requirement: Username enumeration prevention documented
`docs/server-rules.md` SHALL document that the server returns `wrong_password` for both incorrect passwords AND unknown usernames when auth mode is active, to prevent username enumeration.

#### Scenario: Enumeration prevention rule present
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** they SHALL find the rule: "Unknown username in auth mode returns wrong_password, not a distinct 'user not found' error"
