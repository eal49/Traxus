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

    async def test_update_voice_adds_speaker_prefix(self):
        """update_voice() must show voice members in the In Voice section."""
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
            # alice should appear in In Voice section with speaker prefix
            self.assertIn("🔊 alice", markup)
            # bob should NOT appear in the In Voice section
            self.assertNotIn("🔊 bob", markup)
            self.assertIn("bob", markup)

    async def test_update_voice_clears_when_empty(self):
        """Clearing voice users removes the In Voice section."""
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
            self.assertNotIn("🔊", markup)
            self.assertNotIn("In Voice", markup)
            self.assertIn("alice", markup)


# ── Volume bar and keyboard interaction tests ────────────────────────────────

class TestMemberPanelVolume(unittest.IsolatedAsyncioTestCase):

    async def _setup(self):
        app = TraxusApp()
        pilot_ctx = app.run_test()
        pilot = await pilot_ctx.__aenter__()
        await app.switch_screen(ChatScreen())
        await pilot.pause()
        mp = app.screen.query_one("#members", MemberPanel)
        return app, pilot, pilot_ctx, mp

    async def test_default_volume_bar_shows_half_filled(self):
        """Default volume (100%) must render 5 filled + 5 empty blocks."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("█████░░░░░", markup)
            self.assertIn("100%", markup)

    async def test_volume_bar_reflects_set_volume(self):
        """After set_volume(alice, 40), bar should show 2 filled + 8 empty blocks."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            app._audio_engine.set_volume("alice", 40)
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("██░░░░░░░░", markup)
            self.assertIn(" 40%", markup)

    async def test_text_members_have_no_volume_bar(self):
        """Members listed in the text section must not have a volume bar."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_members([{"username": "bob"}])
            mp.update_voice([])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("bob", markup)
            self.assertNotIn("█", markup)
            self.assertNotIn("░", markup)

    async def test_right_arrow_increases_volume(self):
        """Pressing → while MemberPanel is focused must increase volume by 10."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            mp.focus()
            await pilot.pause()

            await pilot.press("right")
            await pilot.pause()

            self.assertEqual(app._audio_engine.get_volume("alice"), 110)

    async def test_left_arrow_decreases_volume(self):
        """Pressing ← while MemberPanel is focused must decrease volume by 10."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            mp.focus()
            await pilot.pause()

            await pilot.press("left")
            await pilot.pause()

            self.assertEqual(app._audio_engine.get_volume("alice"), 90)

    async def test_left_at_0_does_not_go_below_0(self):
        """Pressing ← when volume is 0 must stay at 0."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            app._audio_engine.set_volume("alice", 0)
            mp.focus()
            await pilot.pause()

            await pilot.press("left")
            await pilot.pause()

            self.assertEqual(app._audio_engine.get_volume("alice"), 0)

    async def test_right_at_200_does_not_exceed_200(self):
        """Pressing → when volume is 200 must stay at 200."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}])
            app._audio_engine.set_volume("alice", 200)
            mp.focus()
            await pilot.pause()

            await pilot.press("right")
            await pilot.pause()

            self.assertEqual(app._audio_engine.get_volume("alice"), 200)

    async def test_down_arrow_cycles_cursor(self):
        """Pressing ↓ must move the cursor to the next voice user (wrapping)."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}, {"username": "bob"}])
            mp.focus()
            await pilot.pause()

            self.assertEqual(mp._cursor, 0)
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(mp._cursor, 1)
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(mp._cursor, 0)  # wraps

    async def test_no_crash_with_no_voice_users(self):
        """Arrow keys with no voice users must not raise."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([])
            mp.focus()
            await pilot.pause()

            try:
                await pilot.press("left")
                await pilot.press("right")
                await pilot.press("up")
                await pilot.press("down")
                await pilot.pause()
            except Exception as exc:
                self.fail(f"Arrow key with no voice users raised: {exc}")

    async def test_update_voice_resets_cursor(self):
        """update_voice() must reset the cursor to 0."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.update_voice([{"username": "alice"}, {"username": "bob"}])
            mp._cursor = 1
            mp.update_voice([{"username": "charlie"}])
            await pilot.pause()

            self.assertEqual(mp._cursor, 0)


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
