from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ConnectedClient:
    ws: object                   # websockets ServerConnection
    user_id: str
    username: str
    channels: set[str] = field(default_factory=set)
    voice_channels: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)


class ConnectionManager:
    """
    Owns the authoritative map of connected clients.
    All mutations run inside asyncio tasks — no locks needed because
    asyncio is single-threaded cooperative concurrency.
    """

    def __init__(self) -> None:
        self._clients: dict[str, ConnectedClient] = {}   # user_id → client
        self._nick_to_id: dict[str, str] = {}            # username → user_id

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, ws: object, username: str) -> ConnectedClient:
        user_id = str(uuid.uuid4())
        client = ConnectedClient(ws=ws, user_id=user_id, username=username)
        self._clients[user_id] = client
        self._nick_to_id[username] = user_id
        return client

    def unregister(self, user_id: str) -> ConnectedClient | None:
        client = self._clients.pop(user_id, None)
        if client:
            self._nick_to_id.pop(client.username, None)
        return client

    # ── Lookups ───────────────────────────────────────────────────────────────

    def get_by_id(self, user_id: str) -> ConnectedClient | None:
        return self._clients.get(user_id)

    def is_nick_taken(self, username: str) -> bool:
        return username in self._nick_to_id

    def clients_in_channel(self, channel: str) -> list[ConnectedClient]:
        return [c for c in self._clients.values() if channel in c.channels]

    def voice_clients_in_channel(self, channel: str) -> list[ConnectedClient]:
        return [c for c in self._clients.values() if channel in c.voice_channels]

    def all_clients(self) -> list[ConnectedClient]:
        return list(self._clients.values())

    # ── Nick change ───────────────────────────────────────────────────────────

    def change_nick(self, user_id: str, new_nick: str) -> str:
        """Returns old nick. Raises KeyError if user_id unknown."""
        client = self._clients[user_id]
        old_nick = client.username
        self._nick_to_id.pop(old_nick, None)
        client.username = new_nick
        self._nick_to_id[new_nick] = user_id
        return old_nick

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def send_to(self, user_id: str, payload: dict) -> None:
        client = self._clients.get(user_id)
        if client:
            try:
                await client.ws.send(json.dumps(payload))
            except Exception:
                pass

    async def broadcast_to_channel(
        self,
        channel: str,
        payload: dict,
        exclude_id: str | None = None,
    ) -> None:
        raw = json.dumps(payload)
        for client in self.clients_in_channel(channel):
            if client.user_id == exclude_id:
                continue
            try:
                await client.ws.send(raw)
            except Exception:
                pass

    async def broadcast_to_all(
        self,
        payload: dict,
        exclude_id: str | None = None,
    ) -> None:
        raw = json.dumps(payload)
        for client in list(self._clients.values()):
            if client.user_id == exclude_id:
                continue
            try:
                await client.ws.send(raw)
            except Exception:
                pass
