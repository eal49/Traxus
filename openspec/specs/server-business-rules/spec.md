## ADDED Requirements

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
