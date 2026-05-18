## ADDED Requirements

### Requirement: SQLite database persists channels, messages, and pins
The server SHALL use a SQLite database (via `aiosqlite`) to persist all channel definitions, message history, and pins across restarts. The database file path SHALL be configurable via the `TRAXUS_DB` environment variable, defaulting to `./traxus.db` relative to the working directory.

#### Scenario: Database file created on first run
- **WHEN** the server starts and no database file exists at the configured path
- **THEN** the server SHALL create the database file and initialise the schema (channels, messages, pins tables)

#### Scenario: TRAXUS_DB overrides default path
- **WHEN** the server starts with `TRAXUS_DB=/data/traxus.db`
- **THEN** the database SHALL be opened at `/data/traxus.db`

### Requirement: DatabaseAdapter owns all SQL and connection lifecycle
The server SHALL contain a `server/database.py` module exposing a `DatabaseAdapter` class. This class SHALL own schema initialisation, the `aiosqlite` connection, and all SQL for channels, messages, and pins. No SQL SHALL appear in `ChannelRegistry` or `MessageRouter`.

#### Scenario: Schema initialised idempotently
- **WHEN** `DatabaseAdapter.open()` is called on an existing database
- **THEN** it SHALL use `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` so no error is raised

#### Scenario: WAL mode and foreign keys enabled on open
- **WHEN** `DatabaseAdapter.open()` completes
- **THEN** `PRAGMA journal_mode = WAL` and `PRAGMA foreign_keys = ON` SHALL be active for the connection

### Requirement: Default channels bootstrapped from database on startup
On startup, `ChannelRegistry.load()` SHALL query the database. If the channels table is empty, it SHALL insert the three default channels (`#general`, `#random`, `#dev`) into the database and populate the in-memory registry.

#### Scenario: First-run bootstrap creates default channels
- **WHEN** the server starts with an empty database
- **THEN** `#general`, `#random`, and `#dev` SHALL exist in both the database and the in-memory registry after `load()` completes

#### Scenario: Existing channels loaded on restart
- **WHEN** the server starts with a database containing user-created channels
- **THEN** all channels from the database SHALL be present in the in-memory registry after `load()` completes

### Requirement: Message history is unlimited and persisted
The server SHALL store every chat message in the `messages` table. There SHALL be no cap on the number of messages stored per channel. `get_history(channel, limit, before_ts)` SHALL retrieve up to `limit` messages from the database, ordered by timestamp ascending, optionally bounded above by `before_ts`.

#### Scenario: Messages survive server restart
- **WHEN** a message is sent, the server is restarted, and a new client joins the channel
- **THEN** the client SHALL receive the message in the `joined` history payload

#### Scenario: get_history returns latest N messages by default
- **WHEN** `get_history("general", limit=50)` is called with no `before_ts`
- **THEN** the 50 most recent messages in `#general` are returned, ordered oldest-first

#### Scenario: get_history with before_ts returns older messages
- **WHEN** `get_history("general", limit=50, before_ts=T)` is called with a timestamp T
- **THEN** the 50 most recent messages with `ts < T` are returned, ordered oldest-first

### Requirement: Pins are persisted
The server SHALL store the pinned message for each channel in the `pins` table. `set_pin` SHALL upsert. `get_pin` SHALL query the database.

#### Scenario: Pin survives server restart
- **WHEN** a message is pinned, the server is restarted, and a client joins the channel
- **THEN** the `joined` response SHALL include the pin payload

#### Scenario: Pin replaced by upsert
- **WHEN** `set_pin` is called twice on the same channel
- **THEN** only the second pin SHALL be stored; the first is overwritten

### Requirement: Module-level singletons move into async main
`server/main.py` SHALL construct `DatabaseAdapter`, `ChannelRegistry`, `ConnectionManager`, and `MessageRouter` inside `async def main()` after `await db.open()` and `await chan_reg.load()`. No server-state singletons SHALL be constructed at module level.

#### Scenario: Server starts cleanly with DB initialisation
- **WHEN** `python -m server.main` is run
- **THEN** the server SHALL open the database, load channels, and begin accepting connections without error
