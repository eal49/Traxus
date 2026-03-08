"""Unit tests for server/channel_registry.py."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.channel_registry import ChannelRegistry, Channel, MAX_HISTORY


class TestChannelRegistryBootstrap(unittest.TestCase):

    def setUp(self):
        self.cr = ChannelRegistry()

    def test_general_created(self):
        self.assertTrue(self.cr.exists("general"))

    def test_random_created(self):
        self.assertTrue(self.cr.exists("random"))

    def test_dev_created(self):
        self.assertTrue(self.cr.exists("dev"))

    def test_three_default_channels(self):
        self.assertEqual(len(self.cr.all_channels()), 3)

    def test_nonexistent_channel(self):
        self.assertFalse(self.cr.exists("nonexistent"))

    def test_get_returns_channel_object(self):
        ch = self.cr.get("general")
        self.assertIsInstance(ch, Channel)
        self.assertEqual(ch.name, "general")

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.cr.get("nope"))

    def test_default_topics_set(self):
        self.assertEqual(self.cr.get("general").topic, "General chat")
        self.assertEqual(self.cr.get("random").topic, "Anything goes")
        self.assertEqual(self.cr.get("dev").topic, "Dev discussion")


class TestChannelRegistryCreate(unittest.TestCase):

    def setUp(self):
        self.cr = ChannelRegistry()

    def test_create_returns_channel(self):
        ch = self.cr.create("test", "Test topic", "alice")
        self.assertIsInstance(ch, Channel)

    def test_created_channel_exists(self):
        self.cr.create("test", "Test topic", "alice")
        self.assertTrue(self.cr.exists("test"))

    def test_created_channel_name_correct(self):
        ch = self.cr.create("test", "Test topic", "alice")
        self.assertEqual(ch.name, "test")

    def test_created_channel_topic_correct(self):
        ch = self.cr.create("test", "My topic", "alice")
        self.assertEqual(ch.topic, "My topic")

    def test_created_channel_in_all_channels(self):
        self.cr.create("test", "", "alice")
        names = [c.name for c in self.cr.all_channels()]
        self.assertIn("test", names)

    def test_all_channels_grows(self):
        before = len(self.cr.all_channels())
        self.cr.create("new-one", "", "alice")
        self.assertEqual(len(self.cr.all_channels()), before + 1)


class TestChannelRegistryHistory(unittest.TestCase):

    def setUp(self):
        self.cr = ChannelRegistry()

    def test_new_channel_has_empty_history(self):
        self.assertEqual(self.cr.get_history("general"), [])

    def test_nonexistent_channel_history_is_empty(self):
        self.assertEqual(self.cr.get_history("nope"), [])

    def test_add_single_message(self):
        msg = {"username": "alice", "content": "hi", "ts": 1.0}
        self.cr.add_to_history("general", msg)
        self.assertEqual(self.cr.get_history("general"), [msg])

    def test_multiple_messages_in_order(self):
        msgs = [
            {"username": "alice", "content": "hi", "ts": 1.0},
            {"username": "bob",   "content": "hey", "ts": 2.0},
        ]
        for m in msgs:
            self.cr.add_to_history("general", m)
        self.assertEqual(self.cr.get_history("general"), msgs)

    def test_history_capped_at_max(self):
        for i in range(MAX_HISTORY + 10):
            self.cr.add_to_history("general", {"n": i})
        history = self.cr.get_history("general")
        self.assertEqual(len(history), MAX_HISTORY)

    def test_history_cap_keeps_latest(self):
        for i in range(MAX_HISTORY + 5):
            self.cr.add_to_history("general", {"n": i})
        history = self.cr.get_history("general")
        # Oldest messages should be evicted
        self.assertEqual(history[0]["n"], 5)
        self.assertEqual(history[-1]["n"], MAX_HISTORY + 4)

    def test_add_to_nonexistent_channel_does_nothing(self):
        # Should not raise
        self.cr.add_to_history("ghost", {"content": "x"})

    def test_get_history_returns_copy(self):
        self.cr.add_to_history("general", {"n": 1})
        history = self.cr.get_history("general")
        history.clear()
        # Original should be unaffected
        self.assertEqual(len(self.cr.get_history("general")), 1)


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


class TestChannelSummary(unittest.TestCase):

    def setUp(self):
        self.cr = ChannelRegistry()

    def test_summary_has_name(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=3)
        self.assertEqual(summary["name"], "general")

    def test_summary_has_topic(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=3)
        self.assertEqual(summary["topic"], "General chat")

    def test_summary_has_member_count(self):
        ch = self.cr.get("general")
        summary = self.cr.channel_summary(ch, member_count=7)
        self.assertEqual(summary["member_count"], 7)


if __name__ == "__main__":
    unittest.main()
