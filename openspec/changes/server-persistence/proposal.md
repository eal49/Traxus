## Why

The Traxus server holds all state in memory: channels, message history, and pins are lost on every restart. User-created channels vanish, chat history is gone, and pins disappear. A server restart is indistinguishable from data loss.

## What Changes

- **New**: `server/database.py` — `DatabaseAdapter` class wrapping `aiosqlite`; owns all SQL, schema init, and the connection lifecycle
- **New**: SQLite database file (`traxus.db` by default, configurable via `TRAXUS_DB`) persisting channels, messages, and pins across restarts
- **Modified**: `server/channel_registry.py` — data-access methods (`create`, `vcreate`, `add_to_history`, `get_history`, `set_pin`, `get_pin`) become `async`; `Channel` dataclass loses its `deque` history field; registry seeded from DB on startup
- **Modified**: `server/message_router.py` — adds `await` at the ~8 call sites that now touch async registry methods; no handler logic changes
- **Modified**: `server/main.py` — module-level singletons move inside `async def main()` to allow `await db.open()` and `await chan_reg.load()`
- **Removed**: `MAX_HISTORY` constant and the 50-message cap; history is now unlimited
- **New dependency**: `aiosqlite` (pure Python, stdlib `sqlite3` backed, bundles into the `.exe`)
- **New capability**: channel deletion (`/delete` command) — cascade-delete messages and pins; **BREAKING** for any client expecting a deleted channel to persist across restart (none currently exist)

## Capabilities

### New Capabilities

- `server-persistence`: SQLite-backed durability for channels, message history, and pins via an async `DatabaseAdapter`; unlimited history stored; DB seeded with default channels on first run
- `channel-deletion`: `/delete #channel` command removes a channel and all its messages and pins permanently; server broadcasts `channel_deleted` to all clients

### Modified Capabilities

- `server-business-rules`: history is no longer capped at 50 messages per channel; `get_history` now accepts a `limit` and optional `before_ts` parameter (foundation for scroll-back)
- `websocket-protocol-reference`: new `channel_deleted` S2C message; `joined` response `history` field now returns up to 50 messages by default (configurable); scroll-back `get_history` C2S message reserved for future use

## Impact

- **`server/`**: `database.py` (new), `channel_registry.py`, `message_router.py`, `main.py`
- **`shared/message_types.py`**: new `S2C.CHANNEL_DELETED` and `C2S.DELETE_CHANNEL` constants
- **`client/`**: minimal — client must handle `channel_deleted` broadcast (remove from sidebar, leave if joined)
- **`tests/`**: `test_channel_registry.py` — all test classes become `IsolatedAsyncioTestCase`; `test_message_router.py` — setUp calls that construct `ChannelRegistry` gain async setup; new `test_database.py`
- **`requirements.txt`**: add `aiosqlite`
- **Deploy**: `TRAXUS_DB` env var sets DB path (default `./traxus.db`); existing deployments get a fresh DB on first run (default channels bootstrapped automatically)
