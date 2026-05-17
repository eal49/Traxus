"""Tests for MemberPanel widget — server-roster layout and volume icons."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.widgets.member_panel import (
    MemberPanel, _clip_nick, _volume_icon,
    _MIN_WIDTH, _MAX_WIDTH, _VOICE_OVERHEAD,
)
from client.widgets.message_view import MessageView


def _server_msg(payload: dict) -> TraxusApp.ServerMessage:
    return TraxusApp.ServerMessage(payload)


def _line_count(mv: MessageView) -> int:
    return mv.line_count if hasattr(mv, "line_count") else len(mv.lines)


# ── Nick clipping unit tests ─────────────────────────────────────────────────

class TestClipNick(unittest.TestCase):

    def test_short_nick_unchanged(self):
        self.assertEqual(_clip_nick("alice", 10), "alice")

    def test_exact_length_unchanged(self):
        self.assertEqual(_clip_nick("alice", 5), "alice")

    def test_long_nick_clipped_with_ellipsis(self):
        result = _clip_nick("verylongusername", 10)
        self.assertEqual(result, "verylon...")
        self.assertEqual(len(result), 10)

    def test_clip_at_max_width(self):
        long_nick = "a" * 32
        result = _clip_nick(long_nick, _MAX_WIDTH - _VOICE_OVERHEAD)
        self.assertTrue(result.endswith("..."))
        self.assertLessEqual(len(result), _MAX_WIDTH - _VOICE_OVERHEAD)

    def test_panel_width_clamps_to_max(self):
        mp = MemberPanel()
        long_nick = "a" * 32
        mp._online = [long_nick]
        mp._offline = []
        mp._sorted_voice_users = [long_nick]
        mp._recompute_width()
        self.assertEqual(mp._panel_width, _MAX_WIDTH)

    def test_panel_width_clamps_to_min(self):
        mp = MemberPanel()
        mp._online = []
        mp._offline = []
        mp._sorted_voice_users = []
        mp._recompute_width()
        self.assertEqual(mp._panel_width, _MIN_WIDTH)


# ── Volume icon tier tests (task 9.2) ─────────────────────────────────────────

class TestVolumeIcon(unittest.TestCase):

    def test_zero_is_muted(self):
        self.assertEqual(_volume_icon(0), "🔇")

    def test_one_is_low(self):
        self.assertEqual(_volume_icon(1), "🔈")

    def test_50_is_low(self):
        self.assertEqual(_volume_icon(50), "🔈")

    def test_51_is_medium(self):
        self.assertEqual(_volume_icon(51), "🔉")

    def test_100_is_medium(self):
        self.assertEqual(_volume_icon(100), "🔉")

    def test_149_is_medium(self):
        self.assertEqual(_volume_icon(149), "🔉")

    def test_150_is_high(self):
        self.assertEqual(_volume_icon(150), "🔊")

    def test_200_is_high(self):
        self.assertEqual(_volume_icon(200), "🔊")


# ── MemberPanel server-roster tests (task 9.1) ───────────────────────────────

class TestMemberPanelServerRoster(unittest.IsolatedAsyncioTestCase):

    async def test_online_section_header_shows_count(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice", "bob"], [])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("ONLINE — 2", markup)
            self.assertIn("alice", markup)
            self.assertIn("bob", markup)

    async def test_offline_section_shown_when_populated(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], ["carol"])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("OFFLINE — 1", markup)
            self.assertIn("carol", markup)

    async def test_offline_section_absent_when_empty(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertNotIn("OFFLINE", markup)

    async def test_voice_user_shows_icon_and_percent(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("🔉", markup)
            self.assertIn("100%", markup)

    async def test_non_voice_online_user_has_no_icon(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["bob"], [])
            mp.update_voice([])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("bob", markup)
            self.assertNotIn("🔇", markup)
            self.assertNotIn("🔈", markup)
            self.assertNotIn("🔉", markup)
            self.assertNotIn("🔊", markup)

    async def test_navigation_skips_to_voice_users(self):
        """↓ navigation only stops on voice-active rows."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice", "bob"], [])
            mp.update_voice([{"username": "alice"}, {"username": "bob"}])
            mp.focus()
            await pilot.pause()

            self.assertEqual(mp._cursor, 0)
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(mp._cursor, 1)


# ── Volume adjustment tests ──────────────────────────────────────────────────

class _MockVolumeSource:
    def __init__(self):
        self._v = {}
    def get_volume(self, u): return self._v.get(u, 100)
    def set_volume(self, u, v): self._v[u] = max(0, min(200, v))
    async def close_all(self): pass


class TestMemberPanelVolume(unittest.IsolatedAsyncioTestCase):

    async def test_default_volume_shows_medium_icon(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("🔉", markup)
            self.assertIn("100%", markup)

    async def test_volume_40_shows_low_icon(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            app._peer_manager = _MockVolumeSource()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager.set_volume("alice", 40)
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("🔈", markup)
            self.assertIn("40%", markup)

    async def test_volume_0_shows_muted_icon(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            app._peer_manager = _MockVolumeSource()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager.set_volume("alice", 0)
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("🔇", markup)

    async def test_volume_160_shows_high_icon(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            app._peer_manager = _MockVolumeSource()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager.set_volume("alice", 160)
            await pilot.pause()

            markup = mp._build_markup()
            self.assertIn("🔊", markup)
            self.assertIn("160%", markup)

    async def test_right_arrow_increases_volume(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager = _MockVolumeSource()
            mp.focus()
            await pilot.pause()

            await pilot.press("right")
            await pilot.pause()

            self.assertEqual(app._peer_manager.get_volume("alice"), 110)

    async def test_left_arrow_decreases_volume(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager = _MockVolumeSource()
            mp.focus()
            await pilot.pause()

            await pilot.press("left")
            await pilot.pause()

            self.assertEqual(app._peer_manager.get_volume("alice"), 90)

    async def test_left_at_0_stays_at_0(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager = _MockVolumeSource()
            app._peer_manager.set_volume("alice", 0)
            mp.focus()
            await pilot.pause()

            await pilot.press("left")
            await pilot.pause()

            self.assertEqual(app._peer_manager.get_volume("alice"), 0)

    async def test_right_at_200_stays_at_200(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice"], [])
            mp.update_voice([{"username": "alice"}])
            app._peer_manager = _MockVolumeSource()
            app._peer_manager.set_volume("alice", 200)
            mp.focus()
            await pilot.pause()

            await pilot.press("right")
            await pilot.pause()

            self.assertEqual(app._peer_manager.get_volume("alice"), 200)

    async def test_down_arrow_cycles_cursor(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice", "bob"], [])
            mp.update_voice([{"username": "alice"}, {"username": "bob"}])
            mp.focus()
            await pilot.pause()

            self.assertEqual(mp._cursor, 0)
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(mp._cursor, 1)
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(mp._cursor, 0)

    async def test_no_crash_with_no_voice_users(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members([], [])
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
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            mp = app.screen.query_one("#members", MemberPanel)
            mp.set_server_members(["alice", "bob"], [])
            mp.update_voice([{"username": "alice"}, {"username": "bob"}])
            mp._cursor = 1
            mp.update_voice([{"username": "charlie"}])
            await pilot.pause()

            self.assertEqual(mp._cursor, 0)


# ── App-level user_online / user_offline handler tests (task 9.3) ─────────────

class TestUserPresenceHandlers(unittest.IsolatedAsyncioTestCase):

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_user_online_adds_to_online_set(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)

            app.post_message(_server_msg({"type": "user_online", "username": "alice"}))
            await pilot.pause()

            self.assertIn("alice", app._online_users)

    async def test_user_online_removes_from_offline_set(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._known_offline_users.add("alice")

            app.post_message(_server_msg({"type": "user_online", "username": "alice"}))
            await pilot.pause()

            self.assertNotIn("alice", app._known_offline_users)

    async def test_user_offline_removes_from_online_set(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._online_users.add("alice")

            app.post_message(_server_msg({"type": "user_offline", "username": "alice"}))
            await pilot.pause()

            self.assertNotIn("alice", app._online_users)

    async def test_user_offline_moves_to_known_offline_if_was_online(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._online_users.add("alice")

            app.post_message(_server_msg({"type": "user_offline", "username": "alice"}))
            await pilot.pause()

            self.assertIn("alice", app._known_offline_users)

    async def test_user_offline_unknown_user_not_added_to_offline(self):
        """A user that was never seen online should not end up in known_offline."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)

            app.post_message(_server_msg({"type": "user_offline", "username": "ghost"}))
            await pilot.pause()

            self.assertNotIn("ghost", app._known_offline_users)


# ── /who command tests ───────────────────────────────────────────────────────

class TestWhoCommand(unittest.IsolatedAsyncioTestCase):

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_who_prints_members(self):
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
