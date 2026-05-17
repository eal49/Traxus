from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field

CHANNEL_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
MAX_HISTORY = 50

_DEFAULT_CHANNELS = [
    ("general", "General chat"),
    ("random",  "Anything goes"),
    ("dev",     "Dev discussion"),
]


@dataclass
class Channel:
    name: str
    topic: str
    created_by: str
    type: str = "text"
    created_at: float = field(default_factory=time.time)
    history: deque = field(default_factory=lambda: deque(maxlen=MAX_HISTORY))


class ChannelRegistry:

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._pins: dict[str, dict] = {}
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        for name, topic in _DEFAULT_CHANNELS:
            self._channels[name] = Channel(
                name=name,
                topic=topic,
                created_by="system",
            )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def exists(self, name: str) -> bool:
        return name in self._channels

    def all_channels(self) -> list[Channel]:
        return list(self._channels.values())

    def get_history(self, name: str) -> list[dict]:
        ch = self._channels.get(name)
        return list(ch.history) if ch else []

    # ── Mutations ─────────────────────────────────────────────────────────────

    def create(self, name: str, topic: str, created_by: str) -> Channel:
        ch = Channel(name=name, topic=topic, created_by=created_by)
        self._channels[name] = ch
        return ch

    def vcreate(self, name: str, topic: str, created_by: str) -> Channel:
        ch = Channel(name=name, topic=topic, created_by=created_by, type="voice")
        self._channels[name] = ch
        return ch

    def add_to_history(self, name: str, message: dict) -> None:
        ch = self._channels.get(name)
        if ch:
            ch.history.append(message)

    def set_pin(self, channel: str, payload: dict) -> None:
        self._pins[channel] = payload

    def get_pin(self, channel: str) -> dict | None:
        return self._pins.get(channel)

    # ── Serialisation ─────────────────────────────────────────────────────────

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
