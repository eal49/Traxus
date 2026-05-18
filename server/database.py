from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from server.channel_registry import Channel

_SCHEMA = """
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
"""


class DatabaseAdapter:

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _init_schema(self) -> None:
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    # ── Channels ──────────────────────────────────────────────────────────────

    async def insert_channel(self, ch: "Channel") -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO channels(name, topic, type, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (ch.name, ch.topic, ch.type, ch.created_by, ch.created_at),
        )
        await self._conn.commit()

    async def fetch_channels(self) -> list[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT name, topic, type, created_by, created_at FROM channels ORDER BY created_at"
        ) as cur:
            return await cur.fetchall()

    async def delete_channel(self, name: str) -> None:
        await self._conn.execute("DELETE FROM channels WHERE name = ?", (name,))
        await self._conn.commit()

    # ── Messages ──────────────────────────────────────────────────────────────

    async def insert_message(self, msg: dict) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO messages(msg_id, channel, user_id, username, content, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                msg["msg_id"],
                msg["channel"],
                msg["user_id"],
                msg["username"],
                msg["content"],
                msg["ts"],
            ),
        )
        await self._conn.commit()

    async def fetch_messages(
        self,
        channel: str,
        limit: int = 50,
        before_ts: float | None = None,
    ) -> list[dict]:
        if before_ts is None:
            async with self._conn.execute(
                "SELECT msg_id, channel, user_id, username, content, ts "
                "FROM (SELECT * FROM messages WHERE channel = ? ORDER BY ts DESC LIMIT ?) "
                "ORDER BY ts ASC",
                (channel, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with self._conn.execute(
                "SELECT msg_id, channel, user_id, username, content, ts "
                "FROM (SELECT * FROM messages WHERE channel = ? AND ts < ? ORDER BY ts DESC LIMIT ?) "
                "ORDER BY ts ASC",
                (channel, before_ts, limit),
            ) as cur:
                rows = await cur.fetchall()
        return [
            {
                "type": "chat",
                "msg_id": r["msg_id"],
                "channel": r["channel"],
                "user_id": r["user_id"],
                "username": r["username"],
                "content": r["content"],
                "ts": r["ts"],
            }
            for r in rows
        ]

    # ── Pins ──────────────────────────────────────────────────────────────────

    async def upsert_pin(self, channel: str, payload: dict) -> None:
        await self._conn.execute(
            "INSERT OR REPLACE INTO pins(channel, msg_id, username, content) "
            "VALUES (?, ?, ?, ?)",
            (channel, payload["msg_id"], payload["username"], payload["content"]),
        )
        await self._conn.commit()

    async def fetch_pin(self, channel: str) -> dict | None:
        async with self._conn.execute(
            "SELECT channel, msg_id, username, content FROM pins WHERE channel = ?",
            (channel,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "type": "pin_added",
            "channel": row["channel"],
            "msg_id": row["msg_id"],
            "username": row["username"],
            "content": row["content"],
        }

    async def delete_pin(self, channel: str) -> None:
        await self._conn.execute("DELETE FROM pins WHERE channel = ?", (channel,))
        await self._conn.commit()
