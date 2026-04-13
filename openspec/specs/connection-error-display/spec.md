### Requirement: Connection failure is reported to the user
When a client's initial WebSocket connection attempt fails (before authentication
succeeds), the application SHALL display a human-readable error message on the
login screen and SHALL NOT silently retry in the background.

#### Scenario: Server unreachable
- **WHEN** the user submits the connect form with a URL that cannot be reached
- **THEN** the login screen SHALL display an error message indicating the connection failed
- **THEN** the Connect button SHALL be re-enabled so the user can correct the URL and retry

#### Scenario: Invalid / wrong URL scheme
- **WHEN** the user submits a URL that is syntactically invalid or the server rejects the handshake
- **THEN** the login screen SHALL display an error message
- **THEN** the login form SHALL return to an interactive state

#### Scenario: Connection refused
- **WHEN** the TCP connection is actively refused by the host
- **THEN** the login screen SHALL display an error message
- **THEN** the Connect button SHALL be re-enabled

### Requirement: Error message is human-readable
The error message shown on the login screen SHALL be a short, user-friendly
string (e.g. "Could not connect — check the server address."). It SHALL NOT
expose raw exception type names or full stack traces.

#### Scenario: Raw OS error is sanitised
- **WHEN** the underlying exception is an OSError or WebSocketException
- **THEN** the displayed message SHALL NOT contain Python exception class names
- **THEN** the displayed message SHALL be no longer than one sentence

### Requirement: Successful connections are unaffected
The existing happy path (connection succeeds, auth succeeds, chat screen loads)
SHALL be unchanged.

#### Scenario: Normal login flow
- **WHEN** the user submits valid credentials to a running server
- **THEN** the app SHALL proceed to the chat screen as before with no error shown

### Requirement: Post-auth reconnection is unaffected
If a connection drops after authentication succeeds, the worker SHALL continue
to auto-retry with exponential back-off as before. The new failure-exit
behaviour SHALL apply only to the initial connection attempt (before auth_ok).

#### Scenario: Reconnection after drop
- **WHEN** an authenticated session loses its connection
- **THEN** the worker SHALL attempt to reconnect and display "reconnecting" status in the chat screen
- **THEN** the login screen SHALL NOT be shown
