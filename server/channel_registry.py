from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.database import DatabaseAdapter

CHANNEL_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")

_DEFAULT_CHANNELS = [
    ("general", "General chat"),
    ("random",  "Anything goes"),
    ("dev",     "Dev discussion"),
]

_DEFAULT_NAMES = frozenset(name for name, _ in _DEFAULT_CHANNELS)


@dataclass
class Channel:
    name: str
    topic: str
    created_by: str
    type: str = "text"
    created_at: float = field(default_factory=time.time)


class ChannelRegistry:

    def __init__(self, db: "DatabaseAdapter") -> None:
        self._db = db
        self._channels: dict[str, Channel] = {}

    async def load(self) -> None:
        rows = await self._db.fetch_channels()
        if not rows:
            await self._bootstrap_defaults()
        else:
            for row in rows:
                self._channels[row["name"]] = Channel(
                    name=row["name"],
                    topic=row["topic"],
                    type=row["type"],
                    created_by=row["created_by"],
                    created_at=row["created_at"],
                )

    async def _bootstrap_defaults(self) -> None:
        for name, topic in _DEFAULT_CHANNELS:
            ch = Channel(name=name, topic=topic, created_by="system")
            self._channels[name] = ch
            await self._db.insert_channel(ch)

    # ── Queries (sync — metadata dict only) ──────────────────────────────────

    def get(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def exists(self, name: str) -> bool:
        return name in self._channels

    def all_channels(self) -> list[Channel]:
        return list(self._channels.values())

    # ── Mutations (async — touch DB) ──────────────────────────────────────────

    async def create(self, name: str, topic: str, created_by: str) -> Channel:
        ch = Channel(name=name, topic=topic, created_by=created_by)
        self._channels[name] = ch
        await self._db.insert_channel(ch)
        return ch

    async def vcreate(self, name: str, topic: str, created_by: str) -> Channel:
        ch = Channel(name=name, topic=topic, created_by=created_by, type="voice")
        self._channels[name] = ch
        await self._db.insert_channel(ch)
        return ch

    async def delete(self, name: str) -> None:
        self._channels.pop(name, None)
        await self._db.delete_channel(name)

    async def add_to_history(self, name: str, message: dict) -> None:
        if name in self._channels:
            await self._db.insert_message(message)

    async def get_history(
        self,
        name: str,
        limit: int = 50,
        before_ts: float | None = None,
    ) -> list[dict]:
        if name not in self._channels:
            return []
        return await self._db.fetch_messages(name, limit, before_ts)

    async def set_pin(self, channel: str, payload: dict) -> None:
        await self._db.upsert_pin(channel, payload)

    async def get_pin(self, channel: str) -> dict | None:
        return await self._db.fetch_pin(channel)

    # ── Serialisation (sync) ──────────────────────────────────────────────────

    def channel_summary(self, ch: Channel, member_count: int, voice_members: list[str] | None = None) -> dict:
        d: dict = {
            "name": ch.name,
            "topic": ch.topic,
            "member_count": member_count,
            "type": ch.type,
        }
        if ch.type == "voice":
            d["voice_members"] = voice_members if voice_members is not None else []
        return d

    @staticmethod
    def is_valid_name(name: str) -> bool:
        return bool(CHANNEL_NAME_RE.match(name))

    @staticmethod
    def is_default(name: str) -> bool:
        return name in _DEFAULT_NAMES
