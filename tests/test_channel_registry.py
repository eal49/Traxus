"""Unit tests for server/channel_registry.py."""
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.channel_registry import ChannelRegistry, Channel
from server.database import DatabaseAdapter


async def _make_registry() -> tuple[ChannelRegistry, DatabaseAdapter]:
    db = DatabaseAdapter(":memory:")
    await db.open()
    cr = ChannelRegistry(db)
    await cr.load()
    return cr, db


class TestChannelRegistryBootstrap(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_general_created(self):
        self.assertTrue(self.cr.exists("general"))

    async def test_random_created(self):
        self.assertTrue(self.cr.exists("random"))

    async def test_dev_created(self):
        self.assertTrue(self.cr.exists("dev"))

    async def test_three_default_channels(self):
        self.assertEqual(len(self.cr.all_channels()), 3)

    async def test_nonexistent_channel(self):
        self.assertFalse(self.cr.exists("nonexistent"))

    async def test_get_returns_channel_object(self):
        ch = self.cr.get("general")
        self.assertIsInstance(ch, Channel)
        self.assertEqual(ch.name, "general")

    async def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.cr.get("nope"))

    async def test_default_topics_set(self):
        self.assertEqual(self.cr.get("general").topic, "General chat")
        self.assertEqual(self.cr.get("random").topic, "Anything goes")
        self.assertEqual(self.cr.get("dev").topic, "Dev discussion")

    async def test_load_from_existing_db_restores_channels(self):
        # Simulate restart: new registry on same DB
        cr2 = ChannelRegistry(self.db)
        await cr2.load()
        self.assertTrue(cr2.exists("general"))
        self.assertEqual(len(cr2.all_channels()), 3)

    async def test_load_does_not_duplicate_defaults(self):
        # Load twice on same DB — should not grow
        cr2 = ChannelRegistry(self.db)
        await cr2.load()
        self.assertEqual(len(cr2.all_channels()), 3)


class TestChannelRegistryCreate(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_create_returns_channel(self):
        ch = await self.cr.create("test", "Test topic", "alice")
        self.assertIsInstance(ch, Channel)

    async def test_created_channel_exists(self):
        await self.cr.create("test", "Test topic", "alice")
        self.assertTrue(self.cr.exists("test"))

    async def test_created_channel_name_correct(self):
        ch = await self.cr.create("test", "Test topic", "alice")
        self.assertEqual(ch.name, "test")

    async def test_created_channel_topic_correct(self):
        ch = await self.cr.create("test", "My topic", "alice")
        self.assertEqual(ch.topic, "My topic")

    async def test_created_channel_in_all_channels(self):
        await self.cr.create("test", "", "alice")
        names = [c.name for c in self.cr.all_channels()]
        self.assertIn("test", names)

    async def test_all_channels_grows(self):
        before = len(self.cr.all_channels())
        await self.cr.create("new-one", "", "alice")
        self.assertEqual(len(self.cr.all_channels()), before + 1)

    async def test_created_channel_persisted_to_db(self):
        await self.cr.create("persisted", "topic", "alice")
        rows = await self.db.fetch_channels()
        names = [r["name"] for r in rows]
        self.assertIn("persisted", names)


class TestChannelRegistryDelete(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()
        await self.cr.create("temp", "Temp channel", "alice")

    async def asyncTearDown(self):
        await self.db.close()

    async def test_delete_removes_from_registry(self):
        await self.cr.delete("temp")
        self.assertFalse(self.cr.exists("temp"))

    async def test_delete_removes_from_db(self):
        await self.cr.delete("temp")
        rows = await self.db.fetch_channels()
        names = [r["name"] for r in rows]
        self.assertNotIn("temp", names)

    async def test_delete_nonexistent_no_error(self):
        await self.cr.delete("ghost")

    async def test_is_default_returns_true_for_defaults(self):
        self.assertTrue(ChannelRegistry.is_default("general"))
        self.assertTrue(ChannelRegistry.is_default("random"))
        self.assertTrue(ChannelRegistry.is_default("dev"))

    async def test_is_default_returns_false_for_user_channels(self):
        self.assertFalse(ChannelRegistry.is_default("temp"))


class TestChannelRegistryHistory(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()

    async def asyncTearDown(self):
        await self.db.close()

    def _msg(self, msg_id: str, ts: float = 1.0) -> dict:
        return {
            "type": "chat",
            "msg_id": msg_id,
            "channel": "general",
            "user_id": "u1",
            "username": "alice",
            "content": f"msg {msg_id}",
            "ts": ts,
        }

    async def test_new_channel_has_empty_history(self):
        self.assertEqual(await self.cr.get_history("general"), [])

    async def test_nonexistent_channel_history_is_empty(self):
        self.assertEqual(await self.cr.get_history("nope"), [])

    async def test_add_single_message(self):
        msg = self._msg("m1", ts=1.0)
        await self.cr.add_to_history("general", msg)
        history = await self.cr.get_history("general")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["msg_id"], "m1")

    async def test_multiple_messages_in_order(self):
        await self.cr.add_to_history("general", self._msg("m1", ts=1.0))
        await self.cr.add_to_history("general", self._msg("m2", ts=2.0))
        history = await self.cr.get_history("general")
        self.assertEqual([h["msg_id"] for h in history], ["m1", "m2"])

    async def test_history_unlimited(self):
        for i in range(200):
            await self.cr.add_to_history("general", self._msg(f"m{i}", ts=float(i)))
        history = await self.cr.get_history("general", limit=200)
        self.assertEqual(len(history), 200)

    async def test_history_limit_parameter(self):
        for i in range(10):
            await self.cr.add_to_history("general", self._msg(f"m{i}", ts=float(i)))
        history = await self.cr.get_history("general", limit=5)
        self.assertEqual(len(history), 5)
        # Returns 5 most recent, oldest first
        self.assertEqual(history[0]["ts"], 5.0)

    async def test_history_before_ts(self):
        for i in range(5):
            await self.cr.add_to_history("general", self._msg(f"m{i}", ts=float(i)))
        history = await self.cr.get_history("general", limit=50, before_ts=3.0)
        self.assertTrue(all(h["ts"] < 3.0 for h in history))
        self.assertEqual(len(history), 3)

    async def test_add_to_nonexistent_channel_does_nothing(self):
        msg = self._msg("m1")
        msg["channel"] = "ghost"
        await self.cr.add_to_history("ghost", msg)


class TestChannelRegistryNameValidation(unittest.TestCase):

    def test_simple_lowercase_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("general"))

    def test_with_dashes_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("my-channel"))

    def test_with_underscores_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("my_channel"))

    def test_alphanumeric_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("chan123"))

    def test_max_length_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("a" * 32))

    def test_single_char_valid(self):
        self.assertTrue(ChannelRegistry.is_valid_name("a"))

    def test_empty_string_invalid(self):
        self.assertFalse(ChannelRegistry.is_valid_name(""))

    def test_spaces_invalid(self):
        self.assertFalse(ChannelRegistry.is_valid_name("has spaces"))

    def test_uppercase_invalid(self):
        self.assertFalse(ChannelRegistry.is_valid_name("General"))

    def test_too_long_invalid(self):
        self.assertFalse(ChannelRegistry.is_valid_name("a" * 33))

    def test_special_chars_invalid(self):
        self.assertFalse(ChannelRegistry.is_valid_name("chan!"))
        self.assertFalse(ChannelRegistry.is_valid_name("#channel"))
        self.assertFalse(ChannelRegistry.is_valid_name("chan/sub"))


class TestChannelSummary(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_summary_has_name(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=3)
        self.assertEqual(summary["name"], "general")

    async def test_summary_has_topic(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=3)
        self.assertEqual(summary["topic"], "General chat")

    async def test_summary_has_member_count(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=7)
        self.assertEqual(summary["member_count"], 7)


class TestChannelRegistryPin(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.cr, self.db = await _make_registry()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_get_pin_returns_none_when_no_pin_set(self):
        self.assertIsNone(await self.cr.get_pin("general"))

    async def test_set_pin_stores_payload(self):
        payload = {"msg_id": "abc", "username": "alice", "content": "hello"}
        await self.cr.set_pin("general", payload)
        pin = await self.cr.get_pin("general")
        self.assertEqual(pin["msg_id"], "abc")

    async def test_set_pin_replaces_existing_pin(self):
        await self.cr.set_pin("general", {"msg_id": "old", "username": "alice", "content": "old"})
        await self.cr.set_pin("general", {"msg_id": "new", "username": "bob", "content": "new"})
        pin = await self.cr.get_pin("general")
        self.assertEqual(pin["msg_id"], "new")

    async def test_pin_per_channel_independent(self):
        await self.cr.set_pin("general", {"msg_id": "g1", "username": "alice", "content": "gen"})
        await self.cr.set_pin("random", {"msg_id": "r1", "username": "bob", "content": "rnd"})
        self.assertEqual((await self.cr.get_pin("general"))["msg_id"], "g1")
        self.assertEqual((await self.cr.get_pin("random"))["msg_id"], "r1")

    async def test_get_pin_for_unknown_channel_returns_none(self):
        self.assertIsNone(await self.cr.get_pin("nonexistent"))


if __name__ == "__main__":
    unittest.main()
