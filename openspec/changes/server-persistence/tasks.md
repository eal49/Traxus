## 1. Dependency and Constants

- [x] 1.1 Add `aiosqlite` to `requirements.txt`
- [x] 1.2 Add `S2C.CHANNEL_DELETED = "channel_deleted"` and `C2S.DELETE_CHANNEL = "delete_channel"` to `shared/message_types.py`
- [x] 1.3 Add `ErrorCode.CANNOT_DELETE_DEFAULT = "cannot_delete_default_channel"` to `shared/message_types.py`

## 2. DatabaseAdapter

- [x] 2.1 Create `server/database.py` with `DatabaseAdapter` class: `__init__(self, path: str)`, `async open()`, `async close()`
- [x] 2.2 In `open()`: connect via `aiosqlite`, set `row_factory = aiosqlite.Row`, enable `PRAGMA journal_mode = WAL` and `PRAGMA foreign_keys = ON`, then call `_init_schema()`
- [x] 2.3 Implement `async _init_schema()`: `CREATE TABLE IF NOT EXISTS channels(name, topic, type, created_by, created_at)`, `messages(msg_id, channel FK cascade, user_id, username, content, ts)`, `pins(channel PK FK cascade, msg_id, username, content)`; create index `idx_messages_channel_ts ON messages(channel, ts)`
- [x] 2.4 Implement `async insert_channel(ch: Channel)` and `async fetch_channels() -> list[Row]`
- [x] 2.5 Implement `async delete_channel(name: str)` (single DELETE — cascade handles messages and pins)
- [x] 2.6 Implement `async insert_message(msg: dict)`
- [x] 2.7 Implement `async fetch_messages(channel: str, limit: int = 50, before_ts: float | None = None) -> list[dict]`: returns rows ordered oldest-first; if `before_ts` is set, adds `WHERE ts < before_ts`
- [x] 2.8 Implement `async upsert_pin(channel: str, payload: dict)` (INSERT OR REPLACE) and `async fetch_pin(channel: str) -> dict | None`
- [x] 2.9 Implement `async delete_pin(channel: str)`

## 3. ChannelRegistry Refactor

- [x] 3.1 Remove `history: deque` field from `Channel` dataclass and delete `MAX_HISTORY` constant
- [x] 3.2 Add `db: DatabaseAdapter` parameter to `ChannelRegistry.__init__`; remove `_bootstrap_defaults()` call from `__init__`; remove `_pins` dict
- [x] 3.3 Add `async load()` method: fetch channels from DB; if empty, call `async _bootstrap_defaults()` which inserts default channels into DB and populates `_channels`; else populate `_channels` from DB rows
- [x] 3.4 Make `create()` and `vcreate()` async: insert into DB via `_db.insert_channel()` then update `_channels`
- [x] 3.5 Make `add_to_history()` async: call `_db.insert_message(msg)` (no deque)
- [x] 3.6 Make `get_history()` async, signature `async get_history(name: str, limit: int = 50, before_ts: float | None = None) -> list[dict]`: call `_db.fetch_messages()`; return `[]` if channel does not exist
- [x] 3.7 Make `set_pin()` async: call `_db.upsert_pin()`
- [x] 3.8 Make `get_pin()` async: call `_db.fetch_pin()`
- [x] 3.9 Add `async delete(name: str)`: call `_db.delete_channel(name)`, remove from `_channels`

## 4. MessageRouter Updates

- [x] 4.1 In `_do_join()`, add `await` to `self._chan.get_history()` and `self._chan.get_pin()`
- [x] 4.2 In `_handle_message()`, add `await` to `self._chan.add_to_history()`
- [x] 4.3 In `_handle_create()`, add `await` to `self._chan.create()` / `self._chan.vcreate()`
- [x] 4.4 In `_handle_pin_message()`, add `await` to `self._chan.set_pin()`
- [x] 4.5 Add `_handle_delete_channel()` handler: validate channel exists and is not a default (`general`/`random`/`dev`); call `await self._chan.delete(name)`; broadcast `channel_deleted { channel: name }` to all clients; return client
- [x] 4.6 Register `C2S.DELETE_CHANNEL: self._handle_delete_channel` in `self._handlers`

## 5. main.py Refactor

- [x] 5.1 Move `conn_mgr`, `chan_reg`, and `router` construction inside `async def main()`
- [x] 5.2 Read `TRAXUS_DB` env var (default `./traxus.db`); instantiate `DatabaseAdapter(db_path)`; call `await db.open()` before constructing `ChannelRegistry`
- [x] 5.3 Construct `ChannelRegistry(db)` and call `await chan_reg.load()`
- [x] 5.4 Wrap the `websockets.serve` block in a `try/finally` that calls `await db.close()` on exit

## 6. Client — channel_deleted Handler

- [x] 6.1 Add `S2C.CHANNEL_DELETED` case in `TraxusApp.on_traxus_app_server_message()`: if deleted channel is `current_channel`, join `#general`; call `chat.refresh_channel_list()` or equivalent to remove the channel from the sidebar
- [x] 6.2 In `ChatScreen` / `ChannelSidebar`, ensure `refresh_channels()` called after `channel_deleted` removes the deleted entry (the channel list rebroadcast from the server handles this automatically — verify that the existing `channel_list` handler re-renders the sidebar)

## 7. Tests

- [ ] 7.1 Create `tests/test_database.py`: `IsolatedAsyncioTestCase` tests for `DatabaseAdapter` using `":memory:"` path — cover `insert_channel`, `fetch_channels`, `delete_channel` cascade, `insert_message`, `fetch_messages` (limit, before_ts), `upsert_pin`, `fetch_pin`, `delete_pin`
- [ ] 7.2 Rewrite `tests/test_channel_registry.py`: convert all `TestCase` classes to `IsolatedAsyncioTestCase`; `setUp` → `asyncSetUp` creating `DatabaseAdapter(":memory:")` and `await db.open()`; all test methods become `async def`; replace `MAX_HISTORY` cap tests with unlimited-history tests; add test for `delete()` removing channel from registry
- [x] 7.3 Update `tests/test_message_router.py`: convert the four `setUp` calls that construct `ChannelRegistry` to `asyncSetUp` with `DatabaseAdapter(":memory:")`; add `await` to registry calls in any helper that calls `create()`, `add_to_history()`, etc.; add tests for `delete_channel` handler (success, default channel protection, nonexistent channel)
- [x] 7.4 Add `test_channel_deleted_handler` to `tests/test_app.py`: verify client handles `channel_deleted` broadcast — sidebar clears the channel, current channel switches to `#general` when the active channel is deleted

## 8. Documentation

- [x] 8.1 Update `docs/protocol.md`: add `delete_channel` C2S entry with field table; add `channel_deleted` S2C entry with field table and delivery note; add `cannot_delete_default_channel` to error codes table; add `delete_channel` and `channel_deleted` to the "All C2S/S2C message types" lists
- [x] 8.2 Update `docs/server-rules.md`: replace the 50-message history cap statement with "unlimited SQLite storage, 50 messages sent on join"; add `TRAXUS_DB` configuration note; add channel deletion rule (any user, default channels protected)
