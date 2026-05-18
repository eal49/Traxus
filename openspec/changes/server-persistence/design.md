## Context

The server currently holds all mutable state in three in-memory structures: `ChannelRegistry._channels` (dict of `Channel` objects, each with a `deque(maxlen=50)` for history), `ChannelRegistry._pins` (dict), and `ConnectionManager._clients` (runtime-only, not persisted). Auth accounts already persist to `users.json` via `auth_store`. Everything else resets on restart.

The asyncio event loop is single-threaded. All server mutations happen cooperatively — no locks are needed. This makes a single SQLite file the natural persistence layer: no concurrent writers, no daemon process, no network.

## Goals / Non-Goals

**Goals:**
- Channels, message history, and pins survive server restarts
- Channel deletion with cascade cleanup
- Zero-change client protocol for existing features (joined history, channel_list, pins)
- Foundation for scroll-back (query older messages by cursor timestamp)
- Clean async interface throughout — no blocking SQLite calls on the event loop

**Non-Goals:**
- Scroll-back command (reserved for a follow-on change)
- Message edit or delete (separate change)
- Direct Messages (separate change)
- Multi-server or replicated storage
- Migration tooling for existing deployments (first run bootstraps defaults; no prior data exists)

## Decisions

### D1: aiosqlite over stdlib sqlite3 + run_in_executor

`aiosqlite` wraps `sqlite3` in a dedicated thread and exposes an `async/await` API. The alternative — `loop.run_in_executor(None, sync_call)` with stdlib `sqlite3` — achieves the same result but requires manual thread-safety discipline (`check_same_thread=False`, serialised executor) and is more verbose per call site.

`aiosqlite` is pure Python (~300 lines), has no native dependencies, bundles cleanly into the `.exe`, and is the established community pattern for asyncio + SQLite. Chosen.

### D2: DatabaseAdapter as a standalone class, not embedded in ChannelRegistry

`DatabaseAdapter` owns all SQL, schema init, and the connection lifecycle. `ChannelRegistry` calls it but does not inherit from it or know its internals. This keeps SQL in one place, allows independent testing of the adapter, and leaves ChannelRegistry focused on business logic.

### D3: ChannelRegistry metadata stays in memory; history and pins go to DB

`_channels: dict[str, Channel]` (channel name → metadata) remains in memory. It is loaded once from DB on startup and updated on create/delete. This means `exists()`, `get()`, `all_channels()`, and `channel_summary()` stay **synchronous** — no await needed in `_channel_list_payload()` or anywhere that just inspects channel metadata.

Only DB-touching methods become async: `create`, `vcreate`, `add_to_history`, `get_history`, `set_pin`, `get_pin`, `delete`.

### D4: Remove the deque; DB is the authoritative history

`Channel.history: deque` is removed. `get_history(channel, limit=50, before_ts=None)` queries SQLite directly. At this scale (personal VPS, <50 users) a SQLite indexed query returning 50 rows is indistinguishable from a deque read. The `MAX_HISTORY` constant and the two tests that assert cap behaviour are deleted.

The `before_ts` parameter is added now (default `None`) so the scroll-back command can call `get_history(channel, limit=50, before_ts=cursor)` without any schema or API change.

### D5: Channel deletion broadcasts `channel_deleted` and cleans up via CASCADE

Schema uses `FOREIGN KEY ... ON DELETE CASCADE` so deleting a row from `channels` automatically removes all `messages` and `pins` for that channel. The server then broadcasts `S2C.CHANNEL_DELETED` to all clients. Clients receiving this message leave the channel (if joined) and remove it from the sidebar.

### D6: Module-level singletons move inside async main()

`main.py` currently creates `conn_mgr`, `chan_reg`, and `router` at module level (before the event loop starts). With async DB init (`await db.open()`, `await chan_reg.load()`) these must move inside `async def main()`. `client_handler` closes over `router` as before.

### D7: Schema

```sql
CREATE TABLE IF NOT EXISTS channels (
    name       TEXT PRIMARY KEY,
    topic      TEXT NOT NULL DEFAULT '',
    type       TEXT NOT NULL DEFAULT 'text',
    created_by TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    msg_id   TEXT PRIMARY KEY,
    channel  TEXT NOT NULL REFERENCES channels(name) ON DELETE CASCADE,
    user_id  TEXT NOT NULL,
    username TEXT NOT NULL,
    content  TEXT NOT NULL,
    ts       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_channel_ts ON messages(channel, ts);

CREATE TABLE IF NOT EXISTS pins (
    channel  TEXT PRIMARY KEY REFERENCES channels(name) ON DELETE CASCADE,
    msg_id   TEXT NOT NULL,
    username TEXT NOT NULL,
    content  TEXT NOT NULL
);

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
```

WAL mode improves read concurrency and crash safety. `(channel, ts)` index makes "last 50 messages" queries efficient.

## Risks / Trade-offs

**[Async test rewrite]** All `TestCase` classes that construct `ChannelRegistry` must become `IsolatedAsyncioTestCase`. ~44 tests in `test_channel_registry.py` and ~4 setUp calls in `test_message_router.py`. → Acceptable cost; the test logic is unchanged, only the scaffold changes.

**[Blocking event loop during startup]** `db.open()` and `chan_reg.load()` run before the server accepts connections — blocking here is fine. → No mitigation needed.

**[SQLite write latency on message send]** Each message appends one row to SQLite (~0.1–0.3 ms WAL write). At a personal VPS scale this is invisible. → Acceptable; can add async batching later if needed.

**[No migration from prior state]** Existing deployments have no SQLite DB. First run creates a fresh DB with default channels. Chat history from before this release is lost. → Acceptable; there is no prior persistent history to migrate.

**[Foreign key enforcement]** SQLite does not enforce foreign keys by default. `PRAGMA foreign_keys = ON` must be set on every connection. `DatabaseAdapter.open()` sets this. → Mitigated.

## Migration Plan

1. Deploy new server binary / restart service.
2. Server detects no `TRAXUS_DB` file → creates `traxus.db` in the working directory (or path from `TRAXUS_DB` env var).
3. `ChannelRegistry.load()` finds empty `channels` table → bootstraps `#general`, `#random`, `#dev`.
4. Normal operation resumes. All subsequent messages, channel creates, and pins are persisted.

Rollback: stop service, remove `traxus.db`, revert binary. State returns to prior in-memory behaviour.

## Open Questions

- Should `TRAXUS_DB` default to `./traxus.db` (working directory) or `~/.traxus/traxus.db`? Working directory is simpler for the VPS systemd service setup.
- Should channel deletion be admin-only (auth required) or available to any authenticated user? Initial implementation: any authenticated user; moderation is a separate change.
