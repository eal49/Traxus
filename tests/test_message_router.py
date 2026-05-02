"""
Unit tests for server/message_router.py.

Uses IsolatedAsyncioTestCase so each test runs in a fresh asyncio event loop.
The WebSocket is replaced with MockWs which records all JSON messages sent.
"""
import sys
import os
import json
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.connection_manager import ConnectionManager
from server.channel_registry import ChannelRegistry
from server.message_router import MessageRouter
from shared.message_types import C2S, S2C, AuthError, ErrorCode, VERSION


# ── WebSocket stub ────────────────────────────────────────────────────────────

class MockWs:
    """Records every JSON payload sent via send()."""

    def __init__(self):
        self.sent: list[dict] = []
        self.closed: bool = False

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    async def close(self) -> None:
        self.closed = True

    # Convenience helpers
    def of_type(self, t: str) -> list[dict]:
        return [m for m in self.sent if m.get("type") == t]

    def first_of_type(self, t: str) -> dict | None:
        found = self.of_type(t)
        return found[0] if found else None

    def last(self) -> dict | None:
        return self.sent[-1] if self.sent else None

    def clear(self) -> None:
        self.sent.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_router():
    conn = ConnectionManager()
    chan  = ChannelRegistry()
    router = MessageRouter(conn, chan)
    return router, conn, chan


async def do_auth(router, conn, ws, username="alice"):
    """Perform a successful auth and return the resulting client."""
    return await router.dispatch(
        json.dumps({"type": C2S.AUTH, "username": username, "version": VERSION}),
        ws, None
    )


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()

    async def test_auth_ok_sent(self):
        await do_auth(self.router, self.conn, self.ws)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_OK))

    async def test_auth_ok_username_echoed(self):
        await do_auth(self.router, self.conn, self.ws)
        msg = self.ws.first_of_type(S2C.AUTH_OK)
        self.assertEqual(msg["username"], "alice")

    async def test_auth_ok_user_id_present(self):
        await do_auth(self.router, self.conn, self.ws)
        msg = self.ws.first_of_type(S2C.AUTH_OK)
        self.assertIn("user_id", msg)

    async def test_auth_registers_client(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.assertIsNotNone(client)
        self.assertEqual(client.username, "alice")

    async def test_auto_join_general_after_auth(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.assertIn("general", client.channels)

    async def test_joined_general_sent_after_auth(self):
        await do_auth(self.router, self.conn, self.ws)
        msg = self.ws.first_of_type(S2C.JOINED)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "general")

    async def test_channel_list_sent_after_auth(self):
        await do_auth(self.router, self.conn, self.ws)
        self.assertIsNotNone(self.ws.first_of_type(S2C.CHANNEL_LIST))

    async def test_channel_list_contains_defaults(self):
        await do_auth(self.router, self.conn, self.ws)
        msg = self.ws.first_of_type(S2C.CHANNEL_LIST)
        names = [c["name"] for c in msg["channels"]]
        for name in ("general", "random", "dev"):
            self.assertIn(name, names)

    async def test_auth_error_username_taken(self):
        await do_auth(self.router, self.conn, self.ws)        # alice registered
        ws2 = MockWs()
        await do_auth(self.router, self.conn, ws2, username="alice")
        msg = ws2.first_of_type(S2C.AUTH_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], AuthError.USERNAME_TAKEN)

    async def test_auth_error_empty_username(self):
        client = await router_dispatch(self.router, self.ws, None,
                                       {"type": C2S.AUTH, "username": "", "version": VERSION})
        self.assertIsNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_ERROR))

    async def test_auth_error_username_with_space(self):
        client = await router_dispatch(self.router, self.ws, None,
                                       {"type": C2S.AUTH, "username": "has space", "version": VERSION})
        self.assertIsNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_ERROR))

    async def test_auth_error_username_too_long(self):
        client = await router_dispatch(self.router, self.ws, None,
                                       {"type": C2S.AUTH, "username": "a" * 33, "version": VERSION})
        self.assertIsNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_ERROR))

    async def test_not_authenticated_before_auth(self):
        client = await router_dispatch(self.router, self.ws, None,
                                       {"type": C2S.JOIN, "channel": "general"})
        self.assertIsNone(client)
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.NOT_AUTHENTICATED)

    async def test_invalid_json_returns_error(self):
        await self.router.dispatch("not json {{", self.ws, None)
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.INVALID_JSON)

    async def test_unknown_message_type_returns_error(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()
        await router_dispatch(self.router, self.ws, client,
                              {"type": "totally_unknown"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.UNKNOWN_TYPE)


# ── Join tests ────────────────────────────────────────────────────────────────

class TestJoin(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

    async def test_join_existing_channel(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        msg = self.ws.first_of_type(S2C.JOINED)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "random")

    async def test_join_adds_to_client_channels(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        self.assertIn("random", self.client.channels)

    async def test_join_sends_history(self):
        self.chan.add_to_history("random", {"username": "x", "content": "hi", "ts": 1.0})
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        msg = self.ws.first_of_type(S2C.JOINED)
        self.assertEqual(len(msg["history"]), 1)

    async def test_join_sends_user_list(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        msg = self.ws.first_of_type(S2C.USER_LIST)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "random")

    async def test_join_nonexistent_channel_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "nope"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.NO_SUCH_CHANNEL)

    async def test_join_notifies_existing_members(self):
        ws2 = MockWs()
        bob = await do_auth(self.router, self.conn, ws2, username="bob")
        bob.channels.add("random")
        ws2.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        sys_msgs = ws2.of_type(S2C.SYSTEM)
        self.assertTrue(any("alice" in m.get("content", "") for m in sys_msgs))

    async def test_join_strips_hash_prefix(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "#random"})
        self.assertIn("random", self.client.channels)


# ── Leave tests ───────────────────────────────────────────────────────────────

class TestLeave(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        # Join random explicitly
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.JOIN, "channel": "random"})
        self.ws.clear()

    async def test_leave_sends_left_message(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LEAVE, "channel": "random"})
        msg = self.ws.first_of_type(S2C.LEFT)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "random")

    async def test_leave_removes_from_channels(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LEAVE, "channel": "random"})
        self.assertNotIn("random", self.client.channels)

    async def test_leave_channel_not_in_returns_nothing(self):
        # dev was never joined — should be a no-op
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LEAVE, "channel": "dev"})
        self.assertEqual(len(self.ws.sent), 0)


# ── Message tests ─────────────────────────────────────────────────────────────

class TestMessage(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws_a = MockWs()
        self.ws_b = MockWs()
        self.alice = await do_auth(self.router, self.conn, self.ws_a)
        self.bob   = await do_auth(self.router, self.conn, self.ws_b, username="bob")
        # Put both in general
        self.alice.channels.add("general")
        self.bob.channels.add("general")
        self.ws_a.clear()
        self.ws_b.clear()

    async def test_message_broadcast_to_all_members(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "hello"})
        self.assertIsNotNone(self.ws_a.first_of_type(S2C.CHAT))
        self.assertIsNotNone(self.ws_b.first_of_type(S2C.CHAT))

    async def test_message_content_correct(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "hello world"})
        msg = self.ws_b.first_of_type(S2C.CHAT)
        self.assertEqual(msg["content"], "hello world")

    async def test_message_username_correct(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "hi"})
        msg = self.ws_b.first_of_type(S2C.CHAT)
        self.assertEqual(msg["username"], "alice")

    async def test_message_channel_correct(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "hi"})
        msg = self.ws_b.first_of_type(S2C.CHAT)
        self.assertEqual(msg["channel"], "general")

    async def test_message_has_timestamp(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "hi"})
        msg = self.ws_b.first_of_type(S2C.CHAT)
        self.assertIn("ts", msg)
        self.assertAlmostEqual(msg["ts"], time.time(), delta=5)

    async def test_message_stored_in_history(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": "stored"})
        history = self.chan.get_history("general")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "stored")

    async def test_empty_message_ignored(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "general",
                               "content": ""})
        self.assertEqual(len(self.chan.get_history("general")), 0)
        self.assertEqual(len(self.ws_b.sent), 0)

    async def test_message_to_nonexistent_channel_returns_error(self):
        await router_dispatch(self.router, self.ws_a, self.alice,
                              {"type": C2S.MESSAGE, "channel": "ghost",
                               "content": "hi"})
        self.assertIsNotNone(self.ws_a.first_of_type(S2C.ERROR))


# ── Nick tests ────────────────────────────────────────────────────────────────

class TestNick(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

    async def test_nick_change_broadcasts_nick_changed(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "alice_dev"})
        msg = self.ws.first_of_type(S2C.NICK_CHANGED)
        self.assertIsNotNone(msg)

    async def test_nick_changed_old_nick_correct(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "alice_dev"})
        msg = self.ws.first_of_type(S2C.NICK_CHANGED)
        self.assertEqual(msg["old_nick"], "alice")

    async def test_nick_changed_new_nick_correct(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "alice_dev"})
        msg = self.ws.first_of_type(S2C.NICK_CHANGED)
        self.assertEqual(msg["new_nick"], "alice_dev")

    async def test_nick_updates_conn_mgr(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "alice_dev"})
        self.assertEqual(self.client.username, "alice_dev")
        self.assertTrue(self.conn.is_nick_taken("alice_dev"))
        self.assertFalse(self.conn.is_nick_taken("alice"))

    async def test_nick_taken_returns_error(self):
        ws2 = MockWs()
        await do_auth(self.router, self.conn, ws2, username="bob")
        ws2.clear()
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "bob"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.NICK_TAKEN)

    async def test_nick_with_space_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": "has space"})
        self.assertIsNotNone(self.ws.first_of_type(S2C.ERROR))

    async def test_empty_nick_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.NICK, "new_nick": ""})
        self.assertIsNotNone(self.ws.first_of_type(S2C.ERROR))


# ── Create tests ──────────────────────────────────────────────────────────────

class TestCreate(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

    async def test_create_channel_exists_after(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "new-chan"})
        self.assertTrue(self.chan.exists("new-chan"))

    async def test_create_broadcasts_channel_created(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "new-chan"})
        msg = self.ws.first_of_type(S2C.CHANNEL_CREATED)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "new-chan")

    async def test_create_broadcasts_updated_channel_list(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "new-chan"})
        msg = self.ws.first_of_type(S2C.CHANNEL_LIST)
        names = [c["name"] for c in msg["channels"]]
        self.assertIn("new-chan", names)

    async def test_create_existing_channel_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "general"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.CHANNEL_EXISTS)

    async def test_create_invalid_name_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "Has Spaces"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.INVALID_CHANNEL_NAME)

    async def test_create_strips_hash_prefix(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "#my-chan"})
        self.assertTrue(self.chan.exists("my-chan"))

    async def test_created_by_set_correctly(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.CREATE, "channel": "test-chan"})
        msg = self.ws.first_of_type(S2C.CHANNEL_CREATED)
        self.assertEqual(msg["created_by"], "alice")


# ── Ping / list_channels tests ────────────────────────────────────────────────

class TestPingAndList(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

    async def test_ping_returns_pong(self):
        ts = time.time()
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.PING, "ts": ts})
        msg = self.ws.first_of_type(S2C.PONG)
        self.assertIsNotNone(msg)

    async def test_pong_echoes_timestamp(self):
        ts = 123456.789
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.PING, "ts": ts})
        msg = self.ws.first_of_type(S2C.PONG)
        self.assertAlmostEqual(msg["ts"], ts, places=3)

    async def test_list_channels_returns_channel_list(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LIST_CHANNELS})
        msg = self.ws.first_of_type(S2C.CHANNEL_LIST)
        self.assertIsNotNone(msg)
        self.assertIsInstance(msg["channels"], list)

    async def test_list_channels_includes_all_defaults(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LIST_CHANNELS})
        msg = self.ws.first_of_type(S2C.CHANNEL_LIST)
        names = {c["name"] for c in msg["channels"]}
        self.assertIn("general", names)
        self.assertIn("random", names)
        self.assertIn("dev", names)


# ── list_members tests ────────────────────────────────────────────────────────

class TestListMembers(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

    async def test_list_members_returns_user_list_to_requester_only(self):
        # Second client joins #general so there are two members to list.
        ws2 = MockWs()
        client2 = await do_auth(self.router, self.conn, ws2, username="bob")
        ws2.clear()
        self.ws.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LIST_MEMBERS, "channel": "general"})

        # Requester receives USER_LIST.
        msg = self.ws.first_of_type(S2C.USER_LIST)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "general")
        usernames = {u["username"] for u in msg["users"]}
        self.assertIn("alice", usernames)
        self.assertIn("bob", usernames)

        # Other client receives nothing as a result of this request.
        self.assertEqual(ws2.of_type(S2C.USER_LIST), [])

    async def test_list_members_unknown_channel_returns_error(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.LIST_MEMBERS, "channel": "no-such-channel"})
        msg = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["code"], ErrorCode.NO_SUCH_CHANNEL)


# ── Disconnect tests ──────────────────────────────────────────────────────────

class TestDisconnect(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws_a = MockWs()
        self.ws_b = MockWs()
        self.alice = await do_auth(self.router, self.conn, self.ws_a)
        self.bob   = await do_auth(self.router, self.conn, self.ws_b, username="bob")
        self.ws_a.clear()
        self.ws_b.clear()

    async def test_disconnect_removes_client(self):
        user_id = self.alice.user_id
        await self.router.on_disconnect(self.alice)
        self.assertIsNone(self.conn.get_by_id(user_id))

    async def test_disconnect_frees_nick(self):
        await self.router.on_disconnect(self.alice)
        self.assertFalse(self.conn.is_nick_taken("alice"))

    async def test_disconnect_notifies_channel_members(self):
        # Both in general after auth
        self.ws_b.clear()
        await self.router.on_disconnect(self.alice)
        sys_msgs = self.ws_b.of_type(S2C.SYSTEM)
        self.assertTrue(any("alice" in m.get("content", "") for m in sys_msgs))

    async def test_disconnect_none_client_is_safe(self):
        # on_disconnect(None) should not raise
        await self.router.on_disconnect(None)


# ── Shared dispatch helper ─────────────────────────────────────────────────────

async def router_dispatch(router, ws, client, payload: dict):
    return await router.dispatch(json.dumps(payload), ws, client)


# ── Voice channel tests ────────────────────────────────────────────────────────

class TestVoiceJoin(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        # Create a voice channel
        self.chan.vcreate("lounge", "Voice lounge", "system")
        self.ws.clear()

    async def test_voice_join_success_sends_voice_state(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_JOIN, "channel": "lounge"})
        msg = self.ws.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["channel"], "lounge")

    async def test_voice_join_adds_to_voice_channels(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_JOIN, "channel": "lounge"})
        self.assertIn("lounge", self.client.voice_channels)

    async def test_voice_join_text_channel_returns_not_a_voice_channel(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_JOIN, "channel": "general"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.NOT_A_VOICE_CHANNEL)

    async def test_voice_join_missing_channel_returns_no_such_channel(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_JOIN, "channel": "nope"})
        err = self.ws.first_of_type(S2C.ERROR)
        self.assertIsNotNone(err)
        self.assertEqual(err["code"], ErrorCode.NO_SUCH_CHANNEL)

    async def test_voice_join_notifies_existing_members(self):
        ws2 = MockWs()
        bob = await do_auth(self.router, self.conn, ws2, username="bob")
        bob.voice_channels.add("lounge")
        ws2.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_JOIN, "channel": "lounge"})
        msg = ws2.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(msg)


class TestVoiceLeave(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.client = await do_auth(self.router, self.conn, self.ws)
        self.chan.vcreate("lounge", "Voice lounge", "system")
        self.client.voice_channels.add("lounge")
        self.ws.clear()

    async def test_voice_leave_removes_from_voice_channels(self):
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        self.assertNotIn("lounge", self.client.voice_channels)

    async def test_voice_leave_sends_voice_state_to_remaining(self):
        ws2 = MockWs()
        bob = await do_auth(self.router, self.conn, ws2, username="bob")
        bob.voice_channels.add("lounge")
        ws2.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        msg = ws2.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(msg)

    async def test_voice_leave_user_not_in_remaining_state(self):
        ws2 = MockWs()
        bob = await do_auth(self.router, self.conn, ws2, username="bob")
        bob.voice_channels.add("lounge")
        ws2.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        msg = ws2.first_of_type(S2C.VOICE_STATE)
        usernames = [u["username"] for u in msg.get("users", [])]
        self.assertNotIn("alice", usernames)

    async def test_voice_leave_notifies_leaving_client(self):
        """The leaving client must receive voice_state so it can clear its UI state."""
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        msg = self.ws.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(msg, "leaving client did not receive voice_state")
        self.assertEqual(msg.get("channel"), "lounge")

    async def test_voice_leave_notifies_leaving_client_users_excludes_self(self):
        """voice_state sent to the leaver must not include the leaver in users."""
        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        msg = self.ws.first_of_type(S2C.VOICE_STATE)
        usernames = [u["username"] for u in msg.get("users", [])]
        self.assertNotIn("alice", usernames)

    async def test_voice_leave_with_remaining_user_alice_gets_empty_bob_gets_roster(self):
        """When Alice leaves while Bob remains: Alice gets users=[], Bob gets users=[bob]."""
        ws2 = MockWs()
        bob = await do_auth(self.router, self.conn, ws2, username="bob")
        bob.voice_channels.add("lounge")
        ws2.clear()

        await router_dispatch(self.router, self.ws, self.client,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})

        alice_msg = self.ws.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(alice_msg, "leaving client did not receive voice_state")
        self.assertEqual(alice_msg.get("users"), [],
                         "leaving client must receive empty users list")

        bob_msg = ws2.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(bob_msg, "remaining client did not receive voice_state")
        bob_usernames = [u["username"] for u in bob_msg.get("users", [])]
        self.assertEqual(bob_usernames, ["bob"],
                         "remaining client must see only remaining members")


class TestDisconnectClearsVoice(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()
        self.ws2 = MockWs()
        self.alice = await do_auth(self.router, self.conn, self.ws)
        self.bob = await do_auth(self.router, self.conn, self.ws2, username="bob")
        self.chan.vcreate("lounge", "Voice", "system")
        self.alice.voice_channels.add("lounge")
        self.bob.voice_channels.add("lounge")
        self.ws.clear()
        self.ws2.clear()

    async def test_disconnect_sends_voice_state_to_remaining(self):
        await self.router.on_disconnect(self.alice)
        msg = self.ws2.first_of_type(S2C.VOICE_STATE)
        self.assertIsNotNone(msg)

    async def test_disconnect_removed_user_not_in_voice_state(self):
        await self.router.on_disconnect(self.alice)
        msg = self.ws2.first_of_type(S2C.VOICE_STATE)
        usernames = [u["username"] for u in msg.get("users", [])]
        self.assertNotIn("alice", usernames)


# ── msg_id in chat messages ───────────────────────────────────────────────────

class TestMsgId(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()

    async def test_chat_message_has_msg_id(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.MESSAGE, "channel": "general", "content": "hello",
            }),
            self.ws, client,
        )
        chat = self.ws.first_of_type(S2C.CHAT)
        self.assertIsNotNone(chat)
        self.assertIn("msg_id", chat)
        self.assertIsInstance(chat["msg_id"], str)
        self.assertGreater(len(chat["msg_id"]), 0)

    async def test_msg_ids_are_unique_per_message(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()
        for content in ("msg one", "msg two"):
            await self.router.dispatch(
                json.dumps({
                    "type": C2S.MESSAGE, "channel": "general", "content": content,
                }),
                self.ws, client,
            )
        chats = self.ws.of_type(S2C.CHAT)
        self.assertEqual(len(chats), 2)
        self.assertNotEqual(chats[0]["msg_id"], chats[1]["msg_id"])

    async def test_msg_id_stored_in_history(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.MESSAGE, "channel": "general", "content": "hi",
            }),
            self.ws, client,
        )
        history = self.chan.get_history("general")
        self.assertGreater(len(history), 0)
        self.assertIn("msg_id", history[-1])


# ── pin_message handler ───────────────────────────────────────────────────────

class TestPinMessage(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws = MockWs()

    async def _send_chat_and_get_msg_id(self, client, channel="general", content="pinnable"):
        await self.router.dispatch(
            json.dumps({"type": C2S.MESSAGE, "channel": channel, "content": content}),
            self.ws, client,
        )
        chat = self.ws.of_type(S2C.CHAT)[-1]
        return chat["msg_id"], chat

    async def test_pin_message_broadcasts_pin_added(self):
        client = await do_auth(self.router, self.conn, self.ws)
        msg_id, chat = await self._send_chat_and_get_msg_id(client)
        self.ws.clear()

        await self.router.dispatch(
            json.dumps({
                "type": C2S.PIN_MESSAGE,
                "channel": "general",
                "msg_id": msg_id,
                "username": chat["username"],
                "content": chat["content"],
            }),
            self.ws, client,
        )
        pin = self.ws.first_of_type(S2C.PIN_ADDED)
        self.assertIsNotNone(pin)
        self.assertEqual(pin["msg_id"], msg_id)
        self.assertEqual(pin["channel"], "general")

    async def test_pin_stored_in_channel_registry(self):
        client = await do_auth(self.router, self.conn, self.ws)
        msg_id, chat = await self._send_chat_and_get_msg_id(client)

        await self.router.dispatch(
            json.dumps({
                "type": C2S.PIN_MESSAGE,
                "channel": "general",
                "msg_id": msg_id,
                "username": chat["username"],
                "content": chat["content"],
            }),
            self.ws, client,
        )
        pin = self.chan.get_pin("general")
        self.assertIsNotNone(pin)
        self.assertEqual(pin["msg_id"], msg_id)

    async def test_pin_with_empty_msg_id_ignored(self):
        client = await do_auth(self.router, self.conn, self.ws)
        self.ws.clear()

        await self.router.dispatch(
            json.dumps({
                "type": C2S.PIN_MESSAGE,
                "channel": "general",
                "msg_id": "",
                "content": "whatever",
            }),
            self.ws, client,
        )
        self.assertIsNone(self.ws.first_of_type(S2C.PIN_ADDED))

    async def test_pin_included_in_join_response_after_pin(self):
        client = await do_auth(self.router, self.conn, self.ws)
        msg_id, chat = await self._send_chat_and_get_msg_id(client)

        await self.router.dispatch(
            json.dumps({
                "type": C2S.PIN_MESSAGE,
                "channel": "general",
                "msg_id": msg_id,
                "username": chat["username"],
                "content": chat["content"],
            }),
            self.ws, client,
        )

        # A second client joins — should receive pin in the joined payload
        ws2 = MockWs()
        await do_auth(self.router, self.conn, ws2, username="bob")
        joined = ws2.first_of_type(S2C.JOINED)
        self.assertIsNotNone(joined)
        self.assertIn("pin", joined)
        self.assertEqual(joined["pin"]["msg_id"], msg_id)


if __name__ == "__main__":
    unittest.main()
