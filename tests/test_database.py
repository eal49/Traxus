"""Unit tests for server/database.py (DatabaseAdapter)."""
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.database import DatabaseAdapter
from server.channel_registry import Channel


def _make_channel(name: str, ch_type: str = "text") -> Channel:
    return Channel(name=name, topic=f"Topic {name}", created_by="alice", type=ch_type,
                   created_at=time.time())


def _make_msg(msg_id: str, channel: str, ts: float = 1.0) -> dict:
    return {
        "type": "chat",
        "msg_id": msg_id,
        "channel": channel,
        "user_id": "u1",
        "username": "alice",
        "content": f"msg {msg_id}",
        "ts": ts,
    }


class TestDatabaseAdapterSchema(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = DatabaseAdapter(":memory:")
        await self.db.open()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_open_is_idempotent(self):
        # Second open on a new adapter should not raise
        db2 = DatabaseAdapter(":memory:")
        await db2.open()
        await db2.close()

    async def test_fetch_channels_empty_initially(self):
        rows = await self.db.fetch_channels()
        self.assertEqual(rows, [])


class TestDatabaseAdapterChannels(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = DatabaseAdapter(":memory:")
        await self.db.open()

    async def asyncTearDown(self):
        await self.db.close()

    async def test_insert_and_fetch_channel(self):
        ch = _make_channel("general")
        await self.db.insert_channel(ch)
        rows = await self.db.fetch_channels()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "general")

    async def test_insert_channel_fields_preserved(self):
        ch = _make_channel("dev", ch_type="text")
        await self.db.insert_channel(ch)
        rows = await self.db.fetch_channels()
        row = rows[0]
        self.assertEqual(row["topic"], ch.topic)
        self.assertEqual(row["type"], "text")
        self.assertEqual(row["created_by"], "alice")

    async def test_insert_multiple_channels(self):
        for name in ("general", "random", "dev"):
            await self.db.insert_channel(_make_channel(name))
        rows = await self.db.fetch_channels()
        self.assertEqual(len(rows), 3)

    async def test_insert_or_ignore_duplicate(self):
        ch = _make_channel("general")
        await self.db.insert_channel(ch)
        await self.db.insert_channel(ch)  # should not raise or duplicate
        rows = await self.db.fetch_channels()
        self.assertEqual(len(rows), 1)

    async def test_delete_channel(self):
        await self.db.insert_channel(_make_channel("general"))
        await self.db.delete_channel("general")
        rows = await self.db.fetch_channels()
        self.assertEqual(rows, [])

    async def test_delete_nonexistent_channel_no_error(self):
        await self.db.delete_channel("ghost")  # should not raise


class TestDatabaseAdapterCascade(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = DatabaseAdapter(":memory:")
        await self.db.open()
        await self.db.insert_channel(_make_channel("general"))

    async def asyncTearDown(self):
        await self.db.close()

    async def test_delete_channel_cascades_messages(self):
        await self.db.insert_message(_make_msg("m1", "general"))
        await self.db.insert_message(_make_msg("m2", "general"))
        await self.db.delete_channel("general")
        rows = await self.db.fetch_messages("general")
        self.assertEqual(rows, [])

    async def test_delete_channel_cascades_pin(self):
        await self.db.upsert_pin("general", {"msg_id": "m1", "username": "alice", "content": "hi"})
        await self.db.delete_channel("general")
        pin = await self.db.fetch_pin("general")
        self.assertIsNone(pin)


class TestDatabaseAdapterMessages(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = DatabaseAdapter(":memory:")
        await self.db.open()
        await self.db.insert_channel(_make_channel("general"))

    async def asyncTearDown(self):
        await self.db.close()

    async def test_insert_and_fetch_message(self):
        await self.db.insert_message(_make_msg("m1", "general", ts=1.0))
        rows = await self.db.fetch_messages("general")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["msg_id"], "m1")
        self.assertEqual(rows[0]["content"], "msg m1")

    async def test_fetch_messages_ordered_oldest_first(self):
        for i, ts in enumerate([3.0, 1.0, 2.0]):
            await self.db.insert_message(_make_msg(f"m{i}", "general", ts=ts))
        rows = await self.db.fetch_messages("general")
        self.assertEqual([r["ts"] for r in rows], [1.0, 2.0, 3.0])

    async def test_fetch_messages_limit(self):
        for i in range(10):
            await self.db.insert_message(_make_msg(f"m{i}", "general", ts=float(i)))
        rows = await self.db.fetch_messages("general", limit=5)
        self.assertEqual(len(rows), 5)
        # Should return the 5 most recent (ts 5–9), ordered asc
        self.assertEqual(rows[0]["ts"], 5.0)
        self.assertEqual(rows[-1]["ts"], 9.0)

    async def test_fetch_messages_before_ts(self):
        for i in range(5):
            await self.db.insert_message(_make_msg(f"m{i}", "general", ts=float(i)))
        rows = await self.db.fetch_messages("general", limit=50, before_ts=3.0)
        # Should return ts 0, 1, 2 (< 3.0)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["ts"] < 3.0 for r in rows))

    async def test_fetch_messages_empty_channel(self):
        rows = await self.db.fetch_messages("general")
        self.assertEqual(rows, [])

    async def test_fetch_messages_unknown_channel_returns_empty(self):
        rows = await self.db.fetch_messages("ghost")
        self.assertEqual(rows, [])

    async def test_insert_or_ignore_duplicate_message(self):
        msg = _make_msg("m1", "general")
        await self.db.insert_message(msg)
        await self.db.insert_message(msg)
        rows = await self.db.fetch_messages("general")
        self.assertEqual(len(rows), 1)

    async def test_fetch_messages_type_field_is_chat(self):
        await self.db.insert_message(_make_msg("m1", "general"))
        rows = await self.db.fetch_messages("general")
        self.assertEqual(rows[0]["type"], "chat")


class TestDatabaseAdapterPins(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = DatabaseAdapter(":memory:")
        await self.db.open()
        await self.db.insert_channel(_make_channel("general"))

    async def asyncTearDown(self):
        await self.db.close()

    async def test_fetch_pin_none_when_not_set(self):
        self.assertIsNone(await self.db.fetch_pin("general"))

    async def test_upsert_and_fetch_pin(self):
        payload = {"msg_id": "m1", "username": "alice", "content": "hello"}
        await self.db.upsert_pin("general", payload)
        pin = await self.db.fetch_pin("general")
        self.assertIsNotNone(pin)
        self.assertEqual(pin["msg_id"], "m1")
        self.assertEqual(pin["content"], "hello")

    async def test_upsert_replaces_existing_pin(self):
        await self.db.upsert_pin("general", {"msg_id": "old", "username": "alice", "content": "old"})
        await self.db.upsert_pin("general", {"msg_id": "new", "username": "bob", "content": "new"})
        pin = await self.db.fetch_pin("general")
        self.assertEqual(pin["msg_id"], "new")

    async def test_fetch_pin_type_field_is_pin_added(self):
        await self.db.upsert_pin("general", {"msg_id": "m1", "username": "alice", "content": "hi"})
        pin = await self.db.fetch_pin("general")
        self.assertEqual(pin["type"], "pin_added")

    async def test_delete_pin(self):
        await self.db.upsert_pin("general", {"msg_id": "m1", "username": "alice", "content": "hi"})
        await self.db.delete_pin("general")
        self.assertIsNone(await self.db.fetch_pin("general"))

    async def test_delete_pin_nonexistent_no_error(self):
        await self.db.delete_pin("general")  # should not raise

    async def test_pins_independent_per_channel(self):
        await self.db.insert_channel(_make_channel("random"))
        await self.db.upsert_pin("general", {"msg_id": "g1", "username": "alice", "content": "gen"})
        await self.db.upsert_pin("random", {"msg_id": "r1", "username": "bob", "content": "rnd"})
        self.assertEqual((await self.db.fetch_pin("general"))["msg_id"], "g1")
        self.assertEqual((await self.db.fetch_pin("random"))["msg_id"], "r1")


if __name__ == "__main__":
    unittest.main()
