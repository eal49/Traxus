from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from shared.message_types import C2S, S2C, AuthError, ErrorCode, VERSION
from shared import voice_protocol

if TYPE_CHECKING:
    from server.connection_manager import ConnectedClient, ConnectionManager
    from server.channel_registry import ChannelRegistry

log = logging.getLogger("traxus.router")


class MessageRouter:
    """
    Dispatches decoded JSON messages to the correct async handler.
    Returns the (possibly newly registered) ConnectedClient so the
    server's per-connection loop can track it.
    """

    def __init__(
        self,
        conn_mgr: "ConnectionManager",
        chan_reg: "ChannelRegistry",
    ) -> None:
        self._conn = conn_mgr
        self._chan = chan_reg
        self._handlers = {
            C2S.AUTH:          self._handle_auth,
            C2S.JOIN:          self._handle_join,
            C2S.LEAVE:         self._handle_leave,
            C2S.MESSAGE:       self._handle_message,
            C2S.NICK:          self._handle_nick,
            C2S.CREATE:        self._handle_create,
            C2S.LIST_CHANNELS: self._handle_list_channels,
            C2S.LIST_MEMBERS:  self._handle_list_members,
            C2S.PING:          self._handle_ping,
            C2S.VOICE_JOIN:    self._handle_voice_join,
            C2S.VOICE_LEAVE:   self._handle_voice_leave,
        }

    # ── Entry point ───────────────────────────────────────────────────────────

    async def dispatch(
        self,
        raw: str,
        ws: object,
        client: "ConnectedClient | None",
    ) -> "ConnectedClient | None":
        """Process one raw message. Returns current client (may be set by auth)."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(json.dumps({"type": S2C.ERROR, "code": ErrorCode.INVALID_JSON}))
            return client

        msg_type = payload.get("type", "")

        # Require auth first
        if client is None and msg_type != C2S.AUTH:
            await ws.send(json.dumps({
                "type": S2C.ERROR, "code": ErrorCode.NOT_AUTHENTICATED,
                "message": "Send auth first.",
            }))
            return client

        handler = self._handlers.get(msg_type)
        if handler is None:
            await ws.send(json.dumps({
                "type": S2C.ERROR, "code": ErrorCode.UNKNOWN_TYPE,
                "message": f"Unknown message type: {msg_type!r}",
            }))
            return client

        return await handler(payload, ws, client)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _send(self, ws: object, payload: dict) -> None:
        await ws.send(json.dumps(payload))

    def _channel_list_payload(self) -> dict:
        summaries = []
        for ch in self._chan.all_channels():
            member_count = len(self._conn.clients_in_channel(ch.name))
            summaries.append(self._chan.channel_summary(ch, member_count))
        return {"type": S2C.CHANNEL_LIST, "channels": summaries}

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _handle_auth(self, payload, ws, client):
        client_version = str(payload.get("version", ""))
        if client_version != VERSION:
            await self._send(ws, {
                "type": S2C.AUTH_ERROR, "reason": AuthError.VERSION_MISMATCH,
                "server_version": VERSION, "client_version": client_version,
            })
            await ws.close()
            return client

        username = str(payload.get("username", "")).strip()

        if not username or len(username) > 32 or " " in username:
            await self._send(ws, {
                "type": S2C.AUTH_ERROR, "reason": AuthError.INVALID_USERNAME,
            })
            return client

        if self._conn.is_nick_taken(username):
            await self._send(ws, {
                "type": S2C.AUTH_ERROR, "reason": AuthError.USERNAME_TAKEN,
            })
            return client

        client = self._conn.register(ws, username)
        log.info("AUTH  user=%s id=%s", username, client.user_id)

        await self._send(ws, {
            "type": S2C.AUTH_OK,
            "user_id": client.user_id,
            "username": username,
            "server_version": VERSION,
        })

        # Auto-join #general
        await self._do_join(client, ws, "general")

        # Send full channel list
        await self._send(ws, self._channel_list_payload())

        return client

    async def _handle_join(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        if not self._chan.exists(channel):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NO_SUCH_CHANNEL,
                "message": f"Channel #{channel} does not exist.",
            })
            return client

        await self._do_join(client, ws, channel)
        return client

    async def _do_join(self, client, ws, channel: str) -> None:
        client.channels.add(channel)

        history = self._chan.get_history(channel)
        await self._send(ws, {
            "type": S2C.JOINED,
            "channel": channel,
            "history": history,
        })

        # Build updated member list (includes the newly joined client)
        members = [
            {"user_id": c.user_id, "username": c.username}
            for c in self._conn.clients_in_channel(channel)
        ]
        user_list_payload = {
            "type": S2C.USER_LIST,
            "channel": channel,
            "users": members,
        }
        # Broadcast to ALL channel members so every client's panel stays in sync
        for c in self._conn.clients_in_channel(channel):
            await self._conn.send_to(c.user_id, user_list_payload)

        # Notify others of the join event
        await self._conn.broadcast_to_channel(channel, {
            "type": S2C.SYSTEM,
            "channel": channel,
            "content": f"{client.username} joined #{channel}",
            "ts": time.time(),
        }, exclude_id=client.user_id)

        log.info("JOIN  user=%s channel=#%s", client.username, channel)

    async def _handle_leave(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        if channel not in client.channels:
            return client

        client.channels.discard(channel)
        await self._send(ws, {"type": S2C.LEFT, "channel": channel})

        # Broadcast updated member list to remaining channel members
        members = [
            {"user_id": c.user_id, "username": c.username}
            for c in self._conn.clients_in_channel(channel)
        ]
        await self._conn.broadcast_to_channel(channel, {
            "type": S2C.USER_LIST,
            "channel": channel,
            "users": members,
        })

        await self._conn.broadcast_to_channel(channel, {
            "type": S2C.SYSTEM,
            "channel": channel,
            "content": f"{client.username} left #{channel}",
            "ts": time.time(),
        })
        return client

    async def _handle_message(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        content = str(payload.get("content", "")).strip()

        if not content:
            return client

        if not self._chan.exists(channel):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NO_SUCH_CHANNEL,
                "message": f"Channel #{channel} does not exist.",
            })
            return client

        if channel not in client.channels:
            client.channels.add(channel)

        msg = {
            "type": S2C.CHAT,
            "channel": channel,
            "user_id": client.user_id,
            "username": client.username,
            "content": content,
            "ts": time.time(),
        }
        self._chan.add_to_history(channel, msg)
        await self._conn.broadcast_to_channel(channel, msg)
        log.debug("MSG   #%s <%s> %s", channel, client.username, content[:60])
        return client

    async def _handle_nick(self, payload, ws, client):
        new_nick = str(payload.get("new_nick", "")).strip()

        if not new_nick or len(new_nick) > 32 or " " in new_nick:
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.INVALID_CHANNEL_NAME,
                "message": "Invalid nick.",
            })
            return client

        if self._conn.is_nick_taken(new_nick):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NICK_TAKEN,
                "message": f"Nick '{new_nick}' is already in use.",
            })
            return client

        old_nick = self._conn.change_nick(client.user_id, new_nick)
        log.info("NICK  %s → %s", old_nick, new_nick)

        broadcast = {
            "type": S2C.NICK_CHANGED,
            "old_nick": old_nick,
            "new_nick": new_nick,
            "user_id": client.user_id,
        }
        await self._conn.broadcast_to_all(broadcast)
        return client

    async def _handle_create(self, payload, ws, client):
        name = str(payload.get("channel", "")).strip().lstrip("#")
        channel_type = str(payload.get("channel_type", "text"))

        if not self._chan.is_valid_name(name):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.INVALID_CHANNEL_NAME,
                "message": "Channel name must be 1–32 lowercase alphanumeric/dash/underscore chars.",
            })
            return client

        if self._chan.exists(name):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.CHANNEL_EXISTS,
                "message": f"Channel #{name} already exists.",
            })
            return client

        if channel_type == "voice":
            self._chan.vcreate(name, topic="", created_by=client.username)
        else:
            self._chan.create(name, topic="", created_by=client.username)
        log.info("CREATE #%s (type=%s) by %s", name, channel_type, client.username)

        await self._conn.broadcast_to_all({
            "type": S2C.CHANNEL_CREATED,
            "channel": name,
            "created_by": client.username,
        })
        await self._conn.broadcast_to_all(self._channel_list_payload())
        return client

    async def _handle_list_channels(self, payload, ws, client):
        await self._send(ws, self._channel_list_payload())
        return client

    async def _handle_list_members(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        if not self._chan.exists(channel):
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NO_SUCH_CHANNEL,
                "message": f"Channel #{channel} does not exist.",
            })
            return client
        members = [
            {"user_id": c.user_id, "username": c.username}
            for c in self._conn.clients_in_channel(channel)
        ]
        await self._send(ws, {
            "type": S2C.USER_LIST,
            "channel": channel,
            "users": members,
        })
        return client

    async def _handle_ping(self, payload, ws, client):
        await self._send(ws, {"type": S2C.PONG, "ts": payload.get("ts", time.time())})
        return client

    async def _handle_voice_join(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        ch = self._chan.get(channel)
        if ch is None:
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NO_SUCH_CHANNEL,
                "message": f"Channel #{channel} does not exist.",
            })
            return client
        if ch.type != "voice":
            await self._send(ws, {
                "type": S2C.ERROR, "code": ErrorCode.NOT_A_VOICE_CHANNEL,
                "message": f"#{channel} is not a voice channel.",
            })
            return client

        client.voice_channels.add(channel)
        members = [
            {"user_id": c.user_id, "username": c.username}
            for c in self._conn.voice_clients_in_channel(channel)
        ]
        voice_state = {"type": S2C.VOICE_STATE, "channel": channel, "users": members}
        for vc in self._conn.voice_clients_in_channel(channel):
            await self._conn.send_to(vc.user_id, voice_state)
        log.info("VJOIN user=%s channel=#%s", client.username, channel)
        return client

    async def _handle_voice_leave(self, payload, ws, client):
        channel = str(payload.get("channel", "")).strip().lstrip("#")
        client.voice_channels.discard(channel)
        members = [
            {"user_id": c.user_id, "username": c.username}
            for c in self._conn.voice_clients_in_channel(channel)
        ]
        voice_state = {"type": S2C.VOICE_STATE, "channel": channel, "users": members}
        for vc in self._conn.voice_clients_in_channel(channel):
            await self._conn.send_to(vc.user_id, voice_state)
        log.info("VLEAVE user=%s channel=#%s", client.username, channel)
        return client

    async def relay_voice(self, frame: bytes, ws: object, client: "ConnectedClient") -> None:
        """Relay a binary audio frame to other voice channel members."""
        try:
            n = frame[0]
            channel = frame[1:1 + n].decode()
        except Exception:
            return  # malformed frame — drop silently

        username_bytes = client.username.encode()
        s2c_frame = voice_protocol.pack_c2s(channel, frame[1 + n:])
        # Prepend username: rebuild as S2C frame
        ch_bytes = channel.encode()
        s2c_frame = (
            bytes([len(ch_bytes)]) + ch_bytes +
            bytes([len(username_bytes)]) + username_bytes +
            frame[1 + n:]
        )

        for vc in self._conn.voice_clients_in_channel(channel):
            if vc.ws is ws:
                continue
            try:
                await vc.ws.send(s2c_frame)
            except Exception:
                pass

    # ── Disconnect cleanup ────────────────────────────────────────────────────

    async def on_disconnect(self, client: "ConnectedClient") -> None:
        if client is None:
            return
        channels = list(client.channels)
        voice_channels = list(client.voice_channels)
        self._conn.unregister(client.user_id)
        log.info("QUIT  user=%s", client.username)

        for channel in channels:
            await self._conn.broadcast_to_channel(channel, {
                "type": S2C.SYSTEM,
                "channel": channel,
                "content": f"{client.username} disconnected",
                "ts": time.time(),
            })
            # Broadcast updated member list to remaining channel members
            members = [
                {"user_id": c.user_id, "username": c.username}
                for c in self._conn.clients_in_channel(channel)
            ]
            await self._conn.broadcast_to_channel(channel, {
                "type": S2C.USER_LIST,
                "channel": channel,
                "users": members,
            })

        for channel in voice_channels:
            members = [
                {"user_id": c.user_id, "username": c.username}
                for c in self._conn.voice_clients_in_channel(channel)
            ]
            voice_state = {"type": S2C.VOICE_STATE, "channel": channel, "users": members}
            for vc in self._conn.voice_clients_in_channel(channel):
                await self._conn.send_to(vc.user_id, voice_state)

        # Refresh channel list for everyone
        await self._conn.broadcast_to_all(self._build_channel_list())

    def _build_channel_list(self) -> dict:
        return self._channel_list_payload()
