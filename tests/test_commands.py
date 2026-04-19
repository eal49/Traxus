"""Unit tests for client/commands.py — slash command parser."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.commands import ParsedCommand, parse_input, KNOWN_COMMANDS, HELP_TEXT


class TestParseInput(unittest.TestCase):

    # ── Plain text → None ────────────────────────────────────────────────────

    def test_plain_message_returns_none(self):
        self.assertIsNone(parse_input("hello world"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_input(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(parse_input("   "))

    def test_url_not_a_command(self):
        self.assertIsNone(parse_input("http://example.com"))

    def test_leading_whitespace_stripped_then_plain(self):
        self.assertIsNone(parse_input("  hello"))

    # ── Bare slash → None ────────────────────────────────────────────────────

    def test_lone_slash_returns_none(self):
        self.assertIsNone(parse_input("/"))

    def test_slash_with_spaces_only_returns_none(self):
        self.assertIsNone(parse_input("/   "))

    # ── Command name extracted correctly ──────────────────────────────────────

    def test_help_command(self):
        cmd = parse_input("/help")
        self.assertIsInstance(cmd, ParsedCommand)
        self.assertEqual(cmd.name, "help")
        self.assertEqual(cmd.args, [])

    def test_quit_command(self):
        cmd = parse_input("/quit")
        self.assertEqual(cmd.name, "quit")
        self.assertEqual(cmd.args, [])

    def test_channels_command(self):
        cmd = parse_input("/channels")
        self.assertEqual(cmd.name, "channels")
        self.assertEqual(cmd.args, [])

    # ── Arguments parsed correctly ────────────────────────────────────────────

    def test_join_with_channel(self):
        cmd = parse_input("/join random")
        self.assertEqual(cmd.name, "join")
        self.assertEqual(cmd.args, ["random"])

    def test_join_with_hash_prefix(self):
        cmd = parse_input("/join #random")
        self.assertEqual(cmd.name, "join")
        self.assertEqual(cmd.args, ["#random"])

    def test_nick_with_new_name(self):
        cmd = parse_input("/nick alice_dev")
        self.assertEqual(cmd.name, "nick")
        self.assertEqual(cmd.args, ["alice_dev"])

    def test_create_with_name(self):
        cmd = parse_input("/create new-channel")
        self.assertEqual(cmd.name, "create")
        self.assertEqual(cmd.args, ["new-channel"])

    def test_multiple_args_captured(self):
        cmd = parse_input("/join chan extra ignored")
        self.assertEqual(cmd.name, "join")
        self.assertEqual(cmd.args, ["chan", "extra", "ignored"])

    # ── Case normalisation ────────────────────────────────────────────────────

    def test_command_name_lowercased(self):
        cmd = parse_input("/JOIN random")
        self.assertEqual(cmd.name, "join")

    def test_mixed_case_command(self):
        cmd = parse_input("/Nick Alice")
        self.assertEqual(cmd.name, "nick")
        self.assertEqual(cmd.args, ["Alice"])   # args preserve case

    # ── Surrounding whitespace stripped ──────────────────────────────────────

    def test_leading_spaces_before_slash(self):
        cmd = parse_input("  /help")
        self.assertEqual(cmd.name, "help")

    def test_trailing_spaces_after_command(self):
        cmd = parse_input("/help   ")
        self.assertEqual(cmd.name, "help")
        self.assertEqual(cmd.args, [])

    def test_extra_spaces_between_args(self):
        cmd = parse_input("/join   random")
        self.assertEqual(cmd.name, "join")
        self.assertEqual(cmd.args, ["random"])

    # ── KNOWN_COMMANDS set ────────────────────────────────────────────────────

    def test_known_commands_contains_expected(self):
        for name in ("join", "leave", "nick", "channels", "create", "help", "quit"):
            self.assertIn(name, KNOWN_COMMANDS)

    # ── HELP_TEXT ────────────────────────────────────────────────────────────

    def test_help_text_is_non_empty_string(self):
        self.assertIsInstance(HELP_TEXT, str)
        self.assertGreater(len(HELP_TEXT), 0)

    def test_help_text_mentions_known_commands(self):
        for cmd in ("join", "nick", "quit", "help"):
            self.assertIn(cmd, HELP_TEXT)

    def test_color_in_known_commands(self):
        self.assertIn("color", KNOWN_COMMANDS)

    def test_color_in_help_text(self):
        self.assertIn("color", HELP_TEXT)

    def test_color_blue_parsed(self):
        cmd = parse_input("/color blue")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "color")
        self.assertEqual(cmd.args, ["blue"])

    def test_color_hex_parsed(self):
        cmd = parse_input("/color #ff5500")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "color")
        self.assertEqual(cmd.args, ["#ff5500"])

    def test_color_reset_parsed(self):
        cmd = parse_input("/color reset")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "color")
        self.assertEqual(cmd.args, ["reset"])

    def test_quote_in_known_commands(self):
        self.assertIn("quote", KNOWN_COMMANDS)

    def test_pin_in_known_commands(self):
        self.assertIn("pin", KNOWN_COMMANDS)

    def test_quote_in_help_text(self):
        self.assertIn("quote", HELP_TEXT)

    def test_pin_in_help_text(self):
        self.assertIn("pin", HELP_TEXT)

    def test_audiotest_parsed(self):
        cmd = parse_input("/audioTest")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "audiotest")
        self.assertEqual(cmd.args, [])

    def test_audiotest_in_known_commands(self):
        self.assertIn("audiotest", KNOWN_COMMANDS)

    def test_audiotest_in_help_text(self):
        self.assertIn("audioTest", HELP_TEXT)


if __name__ == "__main__":
    unittest.main()
