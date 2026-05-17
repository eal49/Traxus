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
from shared.message_types import C2S, S2C, AuthError, ErrorCode, PasswordChangeError, VERSION


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


# ── Auth-store integration tests ─────────────────────────────────────────────

try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False


def _make_router_with_store(store):
    """Return a MessageRouter wired to a fake credential store."""
    conn = ConnectionManager()
    chan  = ChannelRegistry()
    return MessageRouter(conn, chan, auth_store=store), conn, chan


def _make_store(username, password, must_change: bool = False):
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return {username: {"hash": hashed, "must_change": must_change}}


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAuthWithCredentials(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.store = _make_store("alice", "correct")
        self.router, self.conn, self.chan = _make_router_with_store(self.store)
        self.ws = MockWs()

    async def test_correct_password_accepted(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice",
                "password": "correct", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNotNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_OK))

    async def test_wrong_password_rejected(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice",
                "password": "wrong", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNone(client)
        msg = self.ws.first_of_type(S2C.AUTH_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], AuthError.WRONG_PASSWORD)
        self.assertTrue(self.ws.closed)

    async def test_missing_password_rejected(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNone(client)
        msg = self.ws.first_of_type(S2C.AUTH_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], AuthError.WRONG_PASSWORD)

    async def test_unknown_username_rejected_with_wrong_password(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "nobody",
                "password": "correct", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNone(client)
        msg = self.ws.first_of_type(S2C.AUTH_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], AuthError.WRONG_PASSWORD)


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAuthNoAuthMode(unittest.IsolatedAsyncioTestCase):
    """No-auth mode: auth_store=None — password field ignored entirely."""

    def setUp(self):
        self.router, self.conn, self.chan = make_router()  # auth_store=None
        self.ws = MockWs()

    async def test_no_auth_mode_accepts_without_password(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNotNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_OK))

    async def test_no_auth_mode_ignores_password_field(self):
        client = await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice",
                "password": "anything", "version": VERSION,
            }),
            self.ws, None,
        )
        self.assertIsNotNone(client)
        self.assertIsNotNone(self.ws.first_of_type(S2C.AUTH_OK))


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAuthMustChangePassword(unittest.IsolatedAsyncioTestCase):
    """auth_ok carries must_change_password when the flag is set."""

    def setUp(self):
        self.ws = MockWs()

    async def test_must_change_password_true_in_auth_ok(self):
        store = _make_store("alice", "correct", must_change=True)
        router, _, _ = _make_router_with_store(store)
        await router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice",
                "password": "correct", "version": VERSION,
            }),
            self.ws, None,
        )
        msg = self.ws.first_of_type(S2C.AUTH_OK)
        self.assertIsNotNone(msg)
        self.assertTrue(msg.get("must_change_password"))

    async def test_must_change_password_absent_when_false(self):
        store = _make_store("alice", "correct", must_change=False)
        router, _, _ = _make_router_with_store(store)
        await router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": "alice",
                "password": "correct", "version": VERSION,
            }),
            self.ws, None,
        )
        msg = self.ws.first_of_type(S2C.AUTH_OK)
        self.assertIsNotNone(msg)
        self.assertFalse(msg.get("must_change_password"))


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestChangePassword(unittest.IsolatedAsyncioTestCase):
    """change_password handler."""

    def setUp(self):
        import tempfile, json as _json, bcrypt as _bcrypt
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmpdir.name, "users.json")
        hashed = _bcrypt.hashpw(b"oldpassword1", _bcrypt.gensalt()).decode()
        with open(self.path, "w") as f:
            _json.dump({"alice": {"hash": hashed, "must_change": False}}, f)
        store = MessageRouter.__new__(MessageRouter)  # don't call __init__
        from server import auth_store as _as
        loaded = _as.load(self.path)
        conn = ConnectionManager()
        chan = ChannelRegistry()
        self.router = MessageRouter(conn, chan, auth_store=loaded, auth_store_path=self.path)
        self.conn = conn
        self.ws = MockWs()

    def tearDown(self):
        self.tmpdir.cleanup()

    async def _auth(self, username="alice", password="oldpassword1") -> object:
        """Authenticate and return the client object."""
        return await self.router.dispatch(
            json.dumps({
                "type": C2S.AUTH, "username": username,
                "password": password, "version": VERSION,
            }),
            self.ws, None,
        )

    async def test_successful_change_sends_password_changed(self):
        client = await self._auth()
        ws2 = MockWs()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.CHANGE_PASSWORD,
                "old_password": "oldpassword1",
                "new_password": "newpassword2",
            }),
            ws2, client,
        )
        self.assertIsNotNone(ws2.first_of_type(S2C.PASSWORD_CHANGED))

    async def test_wrong_old_password_sends_error(self):
        client = await self._auth()
        ws2 = MockWs()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.CHANGE_PASSWORD,
                "old_password": "wrong",
                "new_password": "newpassword2",
            }),
            ws2, client,
        )
        msg = ws2.first_of_type(S2C.PASSWORD_CHANGE_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], PasswordChangeError.WRONG_PASSWORD)

    async def test_too_short_sends_error(self):
        client = await self._auth()
        ws2 = MockWs()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.CHANGE_PASSWORD,
                "old_password": "oldpassword1",
                "new_password": "short",
            }),
            ws2, client,
        )
        msg = ws2.first_of_type(S2C.PASSWORD_CHANGE_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], PasswordChangeError.TOO_SHORT)

    async def test_same_password_sends_error(self):
        client = await self._auth()
        ws2 = MockWs()
        await self.router.dispatch(
            json.dumps({
                "type": C2S.CHANGE_PASSWORD,
                "old_password": "oldpassword1",
                "new_password": "oldpassword1",
            }),
            ws2, client,
        )
        msg = ws2.first_of_type(S2C.PASSWORD_CHANGE_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], PasswordChangeError.SAME_PASSWORD)

    async def test_no_auth_store_sends_auth_disabled(self):
        conn = ConnectionManager()
        chan = ChannelRegistry()
        router_no_auth = MessageRouter(conn, chan, auth_store=None, auth_store_path=None)
        # Register a client without going through auth
        ws = MockWs()
        from server.connection_manager import ConnectedClient
        import uuid
        ws2 = MockWs()
        client = conn.register(ws2, "bob")
        await router_no_auth.dispatch(
            json.dumps({
                "type": C2S.CHANGE_PASSWORD,
                "old_password": "anything",
                "new_password": "newpassword2",
            }),
            ws2, client,
        )
        msg = ws2.first_of_type(S2C.PASSWORD_CHANGE_ERROR)
        self.assertIsNotNone(msg)
        self.assertEqual(msg["reason"], PasswordChangeError.AUTH_DISABLED)


# ── Task 4.3: auth_ok online_users / known_users ──────────────────────────────

class TestAuthOkPresenceFields(unittest.IsolatedAsyncioTestCase):

    async def test_auth_ok_contains_online_users(self):
        router, conn, _ = make_router()
        ws = MockWs()
        await do_auth(router, conn, ws)
        msg = ws.first_of_type(S2C.AUTH_OK)
        self.assertIn("online_users", msg)
        self.assertIsInstance(msg["online_users"], list)

    async def test_auth_ok_online_users_includes_self(self):
        router, conn, _ = make_router()
        ws = MockWs()
        await do_auth(router, conn, ws, username="alice")
        msg = ws.first_of_type(S2C.AUTH_OK)
        self.assertIn("alice", msg["online_users"])

    async def test_auth_ok_online_users_includes_existing_peer(self):
        router, conn, _ = make_router()
        ws_alice = MockWs()
        await do_auth(router, conn, ws_alice, username="alice")
        ws_bob = MockWs()
        await do_auth(router, conn, ws_bob, username="bob")
        msg = ws_bob.first_of_type(S2C.AUTH_OK)
        self.assertIn("alice", msg["online_users"])
        self.assertIn("bob", msg["online_users"])

    async def test_auth_ok_contains_known_users(self):
        router, conn, _ = make_router()
        ws = MockWs()
        await do_auth(router, conn, ws)
        msg = ws.first_of_type(S2C.AUTH_OK)
        self.assertIn("known_users", msg)
        self.assertIsInstance(msg["known_users"], list)

    async def test_auth_ok_known_users_equals_online_when_no_auth_store(self):
        router, conn, _ = make_router()
        ws = MockWs()
        await do_auth(router, conn, ws, username="alice")
        msg = ws.first_of_type(S2C.AUTH_OK)
        self.assertEqual(sorted(msg["online_users"]), sorted(msg["known_users"]))


# ── Task 4.1: user_online / user_offline broadcasts ───────────────────────────

class TestUserOnlineOfflineBroadcasts(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.ws_alice = MockWs()
        self.alice = await do_auth(self.router, self.conn, self.ws_alice, username="alice")
        self.ws_alice.clear()

    async def test_user_online_sent_to_existing_peers_on_new_auth(self):
        ws_bob = MockWs()
        await do_auth(self.router, self.conn, ws_bob, username="bob")
        msgs = self.ws_alice.of_type(S2C.USER_ONLINE)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["username"], "bob")

    async def test_user_online_not_sent_to_authenticating_user_themselves(self):
        ws_bob = MockWs()
        await do_auth(self.router, self.conn, ws_bob, username="bob")
        self.assertEqual(ws_bob.of_type(S2C.USER_ONLINE), [])

    async def test_user_offline_sent_to_remaining_on_disconnect(self):
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        self.ws_alice.clear()
        await self.router.on_disconnect(bob)
        msgs = self.ws_alice.of_type(S2C.USER_OFFLINE)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["username"], "bob")

    async def test_user_offline_contains_correct_username(self):
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        self.ws_alice.clear()
        await self.router.on_disconnect(bob)
        msg = self.ws_alice.of_type(S2C.USER_OFFLINE)[0]
        self.assertEqual(msg["username"], "bob")


# ── Task 4.2: voice_members in channel_list ───────────────────────────────────

class TestChannelListVoiceMembers(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.router, self.conn, self.chan = make_router()
        self.chan.vcreate("lounge", "Voice lounge", "system")
        self.ws_alice = MockWs()
        self.alice = await do_auth(self.router, self.conn, self.ws_alice, username="alice")
        self.ws_alice.clear()

    async def test_channel_list_voice_channel_has_voice_members_key(self):
        cl = self.ws_alice.first_of_type(S2C.CHANNEL_LIST)
        if cl is None:
            await router_dispatch(self.router, self.ws_alice, self.alice,
                                  {"type": C2S.LIST_CHANNELS})
            cl = self.ws_alice.first_of_type(S2C.CHANNEL_LIST)
        voice_entries = [c for c in cl["channels"] if c["type"] == "voice"]
        self.assertTrue(len(voice_entries) > 0)
        for entry in voice_entries:
            self.assertIn("voice_members", entry)

    async def test_text_channel_has_no_voice_members_key(self):
        await router_dispatch(self.router, self.ws_alice, self.alice,
                              {"type": C2S.LIST_CHANNELS})
        cl = self.ws_alice.of_type(S2C.CHANNEL_LIST)[-1]
        text_entries = [c for c in cl["channels"] if c["type"] == "text"]
        for entry in text_entries:
            self.assertNotIn("voice_members", entry)

    async def test_voice_join_rebroadcasts_channel_list_to_all(self):
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        ws_bob.clear()
        self.ws_alice.clear()

        await router_dispatch(self.router, self.ws_alice, self.alice,
                              {"type": C2S.VOICE_JOIN, "channel": "lounge"})

        bob_cl = ws_bob.of_type(S2C.CHANNEL_LIST)
        self.assertGreater(len(bob_cl), 0, "bob should receive channel_list rebroadcast")

    async def test_voice_join_populates_voice_members_in_channel_list(self):
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        ws_bob.clear()

        await router_dispatch(self.router, self.ws_alice, self.alice,
                              {"type": C2S.VOICE_JOIN, "channel": "lounge"})
        cl = ws_bob.of_type(S2C.CHANNEL_LIST)[-1]
        lounge = next(c for c in cl["channels"] if c["name"] == "lounge")
        self.assertIn("alice", lounge["voice_members"])

    async def test_voice_leave_updates_voice_members_in_channel_list(self):
        self.alice.voice_channels.add("lounge")
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        ws_bob.clear()

        await router_dispatch(self.router, self.ws_alice, self.alice,
                              {"type": C2S.VOICE_LEAVE, "channel": "lounge"})
        cl = ws_bob.of_type(S2C.CHANNEL_LIST)[-1]
        lounge = next(c for c in cl["channels"] if c["name"] == "lounge")
        self.assertNotIn("alice", lounge["voice_members"])

    async def test_disconnect_while_in_voice_rebroadcasts_channel_list(self):
        self.alice.voice_channels.add("lounge")
        ws_bob = MockWs()
        bob = await do_auth(self.router, self.conn, ws_bob, username="bob")
        ws_bob.clear()

        await self.router.on_disconnect(self.alice)
        bob_cl = ws_bob.of_type(S2C.CHANNEL_LIST)
        self.assertGreater(len(bob_cl), 0)
        lounge = next(c for c in bob_cl[-1]["channels"] if c["name"] == "lounge")
        self.assertNotIn("alice", lounge.get("voice_members", []))


if __name__ == "__main__":
    unittest.main()
