"""Unit tests for server/connection_manager.py."""
import sys
import os
import asyncio
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.connection_manager import ConnectionManager, ConnectedClient


class MockWs:
    """Minimal WebSocket stub that records sent messages."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def messages_of_type(self, t: str) -> list[dict]:
        return [m for m in self.sent if m.get("type") == t]


class TestConnectionManagerRegister(unittest.TestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.ws = MockWs()

    def test_register_returns_connected_client(self):
        client = self.cm.register(self.ws, "alice")
        self.assertIsInstance(client, ConnectedClient)

    def test_registered_username_correct(self):
        client = self.cm.register(self.ws, "alice")
        self.assertEqual(client.username, "alice")

    def test_registered_ws_correct(self):
        client = self.cm.register(self.ws, "alice")
        self.assertIs(client.ws, self.ws)

    def test_user_id_generated(self):
        client = self.cm.register(self.ws, "alice")
        self.assertIsNotNone(client.user_id)
        self.assertGreater(len(client.user_id), 0)

    def test_channels_initially_empty(self):
        client = self.cm.register(self.ws, "alice")
        self.assertEqual(client.channels, set())

    def test_nick_taken_after_register(self):
        self.cm.register(self.ws, "alice")
        self.assertTrue(self.cm.is_nick_taken("alice"))

    def test_nick_not_taken_before_register(self):
        self.assertFalse(self.cm.is_nick_taken("alice"))

    def test_two_clients_distinct_user_ids(self):
        ws2 = MockWs()
        c1 = self.cm.register(self.ws, "alice")
        c2 = self.cm.register(ws2, "bob")
        self.assertNotEqual(c1.user_id, c2.user_id)

    def test_get_by_id_after_register(self):
        client = self.cm.register(self.ws, "alice")
        found = self.cm.get_by_id(client.user_id)
        self.assertIs(found, client)

    def test_get_by_id_unknown_returns_none(self):
        self.assertIsNone(self.cm.get_by_id("nonexistent"))

    def test_all_clients_grows(self):
        self.assertEqual(len(self.cm.all_clients()), 0)
        self.cm.register(self.ws, "alice")
        self.assertEqual(len(self.cm.all_clients()), 1)
        self.cm.register(MockWs(), "bob")
        self.assertEqual(len(self.cm.all_clients()), 2)


class TestConnectionManagerUnregister(unittest.TestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.ws = MockWs()
        self.client = self.cm.register(self.ws, "alice")

    def test_unregister_returns_client(self):
        result = self.cm.unregister(self.client.user_id)
        self.assertIs(result, self.client)

    def test_unregister_removes_from_clients(self):
        self.cm.unregister(self.client.user_id)
        self.assertIsNone(self.cm.get_by_id(self.client.user_id))

    def test_unregister_frees_nick(self):
        self.cm.unregister(self.client.user_id)
        self.assertFalse(self.cm.is_nick_taken("alice"))

    def test_unregister_unknown_returns_none(self):
        result = self.cm.unregister("ghost")
        self.assertIsNone(result)

    def test_all_clients_shrinks(self):
        self.cm.unregister(self.client.user_id)
        self.assertEqual(len(self.cm.all_clients()), 0)

    def test_double_unregister_is_safe(self):
        self.cm.unregister(self.client.user_id)
        # Should not raise
        result = self.cm.unregister(self.client.user_id)
        self.assertIsNone(result)


class TestConnectionManagerNick(unittest.TestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.ws = MockWs()
        self.client = self.cm.register(self.ws, "alice")

    def test_change_nick_returns_old_nick(self):
        old = self.cm.change_nick(self.client.user_id, "alice_dev")
        self.assertEqual(old, "alice")

    def test_change_nick_updates_client_username(self):
        self.cm.change_nick(self.client.user_id, "alice_dev")
        self.assertEqual(self.client.username, "alice_dev")

    def test_old_nick_freed_after_change(self):
        self.cm.change_nick(self.client.user_id, "alice_dev")
        self.assertFalse(self.cm.is_nick_taken("alice"))

    def test_new_nick_taken_after_change(self):
        self.cm.change_nick(self.client.user_id, "alice_dev")
        self.assertTrue(self.cm.is_nick_taken("alice_dev"))

    def test_change_nick_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.cm.change_nick("ghost", "newname")


class TestConnectionManagerChannelMembership(unittest.TestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.ws_a = MockWs()
        self.ws_b = MockWs()
        self.alice = self.cm.register(self.ws_a, "alice")
        self.bob   = self.cm.register(self.ws_b, "bob")

    def test_clients_in_channel_empty_initially(self):
        self.assertEqual(self.cm.clients_in_channel("general"), [])

    def test_clients_in_channel_after_join(self):
        self.alice.channels.add("general")
        result = self.cm.clients_in_channel("general")
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], self.alice)

    def test_clients_in_channel_multiple_members(self):
        self.alice.channels.add("general")
        self.bob.channels.add("general")
        result = self.cm.clients_in_channel("general")
        self.assertEqual(len(result), 2)

    def test_clients_in_channel_filters_non_members(self):
        self.alice.channels.add("general")
        self.bob.channels.add("random")
        result = self.cm.clients_in_channel("general")
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], self.alice)

    def test_clients_in_channel_after_leave(self):
        self.alice.channels.add("general")
        self.alice.channels.discard("general")
        self.assertEqual(self.cm.clients_in_channel("general"), [])


class TestConnectionManagerBroadcast(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cm = ConnectionManager()
        self.ws_a = MockWs()
        self.ws_b = MockWs()
        self.ws_c = MockWs()
        self.alice = self.cm.register(self.ws_a, "alice")
        self.bob   = self.cm.register(self.ws_b, "bob")
        self.carol = self.cm.register(self.ws_c, "carol")
        self.alice.channels.add("general")
        self.bob.channels.add("general")
        # carol is in a different channel

    async def test_broadcast_reaches_all_members(self):
        payload = {"type": "chat", "content": "hi"}
        await self.cm.broadcast_to_channel("general", payload)
        self.assertEqual(len(self.ws_a.sent), 1)
        self.assertEqual(len(self.ws_b.sent), 1)

    async def test_broadcast_excludes_non_members(self):
        payload = {"type": "chat", "content": "hi"}
        await self.cm.broadcast_to_channel("general", payload)
        self.assertEqual(len(self.ws_c.sent), 0)

    async def test_broadcast_exclude_sender(self):
        payload = {"type": "chat", "content": "hi"}
        await self.cm.broadcast_to_channel(
            "general", payload, exclude_id=self.alice.user_id
        )
        self.assertEqual(len(self.ws_a.sent), 0)   # excluded
        self.assertEqual(len(self.ws_b.sent), 1)    # received

    async def test_broadcast_payload_correct(self):
        payload = {"type": "chat", "content": "hello"}
        await self.cm.broadcast_to_channel("general", payload)
        self.assertEqual(self.ws_a.sent[0]["content"], "hello")

    async def test_send_to_reaches_specific_client(self):
        payload = {"type": "system", "content": "private"}
        await self.cm.send_to(self.alice.user_id, payload)
        self.assertEqual(len(self.ws_a.sent), 1)
        self.assertEqual(len(self.ws_b.sent), 0)

    async def test_send_to_unknown_id_does_not_raise(self):
        await self.cm.send_to("ghost", {"type": "ping"})

    async def test_broadcast_to_all_reaches_all_clients(self):
        payload = {"type": "channel_list", "channels": []}
        await self.cm.broadcast_to_all(payload)
        self.assertEqual(len(self.ws_a.sent), 1)
        self.assertEqual(len(self.ws_b.sent), 1)
        self.assertEqual(len(self.ws_c.sent), 1)

    async def test_broadcast_to_all_with_exclusion(self):
        payload = {"type": "nick_changed"}
        await self.cm.broadcast_to_all(payload, exclude_id=self.bob.user_id)
        self.assertEqual(len(self.ws_a.sent), 1)
        self.assertEqual(len(self.ws_b.sent), 0)   # excluded
        self.assertEqual(len(self.ws_c.sent), 1)


if __name__ == "__main__":
    unittest.main()
