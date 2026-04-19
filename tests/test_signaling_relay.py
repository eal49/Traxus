"""
Unit tests for server signaling relay handlers (task 12.6).

Tests _handle_voice_signal for:
  - offer/answer/ICE relay to named peer
  - from_user overwritten to authenticated sender (anti-spoofing)
  - target-not-found: silently dropped, no error sent
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.message_router import MessageRouter
from server.connection_manager import ConnectedClient
from shared.message_types import C2S, S2C


def _make_client(username: str = "alice", user_id: str = "uid-alice") -> ConnectedClient:
    client = ConnectedClient.__new__(ConnectedClient)
    client.username = username
    client.user_id = user_id
    client.channels = set()
    client.voice_channels = set()
    client.ws = AsyncMock()
    client.ws.send = AsyncMock()
    return client


def _make_router(sender: ConnectedClient, target: ConnectedClient | None):
    """Build a MessageRouter with mocked ConnectionManager and ChannelRegistry."""
    conn = MagicMock()
    conn.get_client_by_username = MagicMock(return_value=target)
    conn.send_to = AsyncMock()

    chan = MagicMock()
    chan.all_channels.return_value = []

    return MessageRouter(conn, chan), conn


class TestVoiceSignalRelay(unittest.IsolatedAsyncioTestCase):

    async def test_offer_forwarded_to_target(self):
        sender = _make_client("alice", "uid-alice")
        target = _make_client("bob", "uid-bob")
        router, conn = _make_router(sender, target)

        payload = {
            "type": C2S.VOICE_OFFER,
            "to_user": "bob",
            "sdp": "v=0\r\n...",
        }
        await router._handle_voice_signal(payload, sender.ws, sender)

        conn.send_to.assert_awaited_once()
        call_args = conn.send_to.call_args
        sent_uid = call_args[0][0]
        sent_payload = call_args[0][1]
        self.assertEqual(sent_uid, "uid-bob")
        self.assertEqual(sent_payload["type"], C2S.VOICE_OFFER)
        self.assertEqual(sent_payload["sdp"], "v=0\r\n...")

    async def test_answer_forwarded_to_target(self):
        sender = _make_client("bob", "uid-bob")
        target = _make_client("alice", "uid-alice")
        router, conn = _make_router(sender, target)

        payload = {"type": C2S.VOICE_ANSWER, "to_user": "alice", "sdp": "answer-sdp"}
        await router._handle_voice_signal(payload, sender.ws, sender)

        conn.send_to.assert_awaited_once()
        sent_payload = conn.send_to.call_args[0][1]
        self.assertEqual(sent_payload["type"], C2S.VOICE_ANSWER)

    async def test_ice_forwarded_to_target(self):
        sender = _make_client("alice", "uid-alice")
        target = _make_client("bob", "uid-bob")
        router, conn = _make_router(sender, target)

        payload = {
            "type": C2S.VOICE_ICE,
            "to_user": "bob",
            "candidate": "candidate:1 1 UDP ...",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
        }
        await router._handle_voice_signal(payload, sender.ws, sender)

        conn.send_to.assert_awaited_once()
        sent_payload = conn.send_to.call_args[0][1]
        self.assertEqual(sent_payload["candidate"], "candidate:1 1 UDP ...")

    async def test_from_user_overwritten_with_sender_username(self):
        """Sender cannot spoof from_user; it must be overwritten server-side."""
        sender = _make_client("alice", "uid-alice")
        target = _make_client("bob", "uid-bob")
        router, conn = _make_router(sender, target)

        payload = {
            "type": C2S.VOICE_OFFER,
            "to_user": "bob",
            "from_user": "EVIL-IMPERSONATOR",
            "sdp": "...",
        }
        await router._handle_voice_signal(payload, sender.ws, sender)

        sent_payload = conn.send_to.call_args[0][1]
        self.assertEqual(
            sent_payload["from_user"],
            "alice",
            "from_user must be overwritten to the authenticated sender's username",
        )

    async def test_target_not_found_drops_silently(self):
        """If target user is not connected, the message is dropped, no error sent."""
        sender = _make_client("alice", "uid-alice")
        router, conn = _make_router(sender, target=None)

        ws_mock = AsyncMock()
        payload = {"type": C2S.VOICE_OFFER, "to_user": "ghost", "sdp": "..."}
        await router._handle_voice_signal(payload, ws_mock, sender)

        conn.send_to.assert_not_awaited()
        ws_mock.send.assert_not_awaited()

    async def test_dispatch_routes_voice_offer(self):
        """dispatch() must route voice_offer to _handle_voice_signal."""
        sender = _make_client("alice", "uid-alice")
        target = _make_client("bob", "uid-bob")
        router, conn = _make_router(sender, target)

        raw = json.dumps({
            "type": C2S.VOICE_OFFER,
            "to_user": "bob",
            "sdp": "test-sdp",
        })
        await router.dispatch(raw, sender.ws, sender)

        conn.send_to.assert_awaited_once()
        sent_payload = conn.send_to.call_args[0][1]
        self.assertEqual(sent_payload["from_user"], "alice")

    async def test_dispatch_routes_voice_answer(self):
        sender = _make_client("bob", "uid-bob")
        target = _make_client("alice", "uid-alice")
        router, conn = _make_router(sender, target)

        raw = json.dumps({"type": C2S.VOICE_ANSWER, "to_user": "alice", "sdp": "a-sdp"})
        await router.dispatch(raw, sender.ws, sender)

        conn.send_to.assert_awaited_once()

    async def test_dispatch_routes_voice_ice(self):
        sender = _make_client("alice", "uid-alice")
        target = _make_client("bob", "uid-bob")
        router, conn = _make_router(sender, target)

        raw = json.dumps({
            "type": C2S.VOICE_ICE,
            "to_user": "bob",
            "candidate": "c",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
        })
        await router.dispatch(raw, sender.ws, sender)

        conn.send_to.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
