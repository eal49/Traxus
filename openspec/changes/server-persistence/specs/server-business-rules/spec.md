## MODIFIED Requirements

### Requirement: History and state invariants documented
The `docs/server-rules.md` file SHALL document the server's stateful guarantees.

#### Scenario: History persistence documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: message history is stored in SQLite with no per-channel cap; up to 50 messages are sent to clients on join (configurable via `get_history` limit)

#### Scenario: Auto-join behaviour documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: upon successful auth, the server automatically joins the client to #general without requiring an explicit join message

#### Scenario: Disconnect cleanup documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: on disconnect, the server removes the client from all channel memberships, frees the username, and broadcasts a `system` disconnect notice to each channel the client was in

#### Scenario: Database configuration documented
- **WHEN** a developer reads `docs/server-rules.md`
- **THEN** the document SHALL state: the server reads `TRAXUS_DB` for the SQLite file path (default `./traxus.db`); channels, messages, and pins persist across restarts

## REMOVED Requirements

### Requirement: History cap of 50 messages
**Reason**: History is now stored in SQLite with no cap. The 50-message limit was an in-memory workaround, not a product requirement.
**Migration**: No client-facing change. Clients still receive up to 50 messages on join. The removal of the cap is internal.
