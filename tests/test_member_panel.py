"""Tests for MemberPanel widget and /who command integration."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.widgets.member_panel import MemberPanel
from client.widgets.message_view import MessageView


def _server_msg(payload: dict) -> TraxusApp.ServerMessage:
    return TraxusApp.ServerMessage(payload)


def _line_count(mv: MessageView) -> int:
    return mv.line_count if hasattr(mv, "line_count") else len(mv.lines)


# ── MemberPanel widget tests ─────────────────────────────────────────────────

class TestMemberPanel(unittest.IsolatedAsyncioTestCase):

    async def test_set_members_updates_content(self):
        """set_members() must render all usernames."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_members([
                {"user_id": "1", "username": "alice"},
                {"user_id": "2", "username": "bob"},
            ])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("alice", markup)
            self.assertIn("bob", markup)

    async def test_update_voice_adds_mic_prefix(self):
        """update_voice() must prefix voice members with mic emoji."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_members([
                {"user_id": "1", "username": "alice"},
                {"user_id": "2", "username": "bob"},
            ])
            mp.update_voice([{"user_id": "1", "username": "alice"}])
            await pilot.pause()

            markup = mp._build_markup()
            # alice should have mic prefix
            self.assertIn("🎤 alice", markup)
            # bob should NOT have mic prefix
            self.assertNotIn("🎤 bob", markup)
            self.assertIn("bob", markup)

    async def test_update_voice_clears_when_empty(self):
        """Clearing voice users removes all mic prefixes."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_members([{"user_id": "1", "username": "alice"}])
            mp.update_voice([{"user_id": "1", "username": "alice"}])
            mp.update_voice([])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertNotIn("🎤", markup)
            self.assertIn("alice", markup)


# ── App-level member state tests ─────────────────────────────────────────────

class TestMemberState(unittest.IsolatedAsyncioTestCase):

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_user_list_stores_members(self):
        """user_list message must populate _channel_members."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)

            app.post_message(_server_msg({
                "type": "user_list",
                "channel": "general",
                "users": [
                    {"user_id": "1", "username": "alice"},
                    {"user_id": "2", "username": "bob"},
                ],
            }))
            await pilot.pause()

            self.assertIn("general", app._channel_members)
            names = [m["username"] for m in app._channel_members["general"]]
            self.assertIn("alice", names)
            self.assertIn("bob", names)

    async def test_user_list_updates_panel(self):
        """user_list for active channel must update MemberPanel."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_channel = "general"

            app.post_message(_server_msg({
                "type": "user_list",
                "channel": "general",
                "users": [{"user_id": "1", "username": "alice"}],
            }))
            await pilot.pause()

            mp = app.screen.query_one("#members", MemberPanel)
            self.assertIn("alice", mp._build_markup())

    async def test_nick_changed_updates_members(self):
        """nick_changed must update username in _channel_members."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._channel_members["general"] = [
                {"user_id": "1", "username": "alice"},
            ]
            app.current_channel = "general"

            app.post_message(_server_msg({
                "type": "nick_changed",
                "old_nick": "alice",
                "new_nick": "alice_dev",
                "user_id": "1",
            }))
            await pilot.pause()

            names = [m["username"] for m in app._channel_members["general"]]
            self.assertIn("alice_dev", names)
            self.assertNotIn("alice", names)


# ── /who command tests ───────────────────────────────────────────────────────

class TestWhoCommand(unittest.IsolatedAsyncioTestCase):

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_who_prints_members(self):
        """/who must print member names in MessageView."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_channel = "general"
            app._channel_members["general"] = [
                {"user_id": "1", "username": "alice"},
                {"user_id": "2", "username": "bob"},
            ]

            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/who")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_who_no_members_shows_info(self):
        """/who with no member data shows an info message."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_channel = "general"

            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/who")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)


# ── parse_input /who test ────────────────────────────────────────────────────

class TestParseWho(unittest.TestCase):

    def test_parse_who(self):
        from client.commands import parse_input, ParsedCommand
        cmd = parse_input("/who")
        self.assertIsInstance(cmd, ParsedCommand)
        self.assertEqual(cmd.name, "who")
        self.assertEqual(cmd.args, [])


if __name__ == "__main__":
    unittest.main()
