"""
Tests for client/app.py — screen routing, _chat() helper, and server-message
dispatch.

The key regression this suite guards against:
  _chat() must use self.screen (not query_one(ChatScreen)) so that it reliably
  returns the active ChatScreen.  When query_one() was used, it silently returned
  None and every "if chat:" guard became a no-op, making all commands invisible
  in the UI even though the server received them.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.login_screen import LoginScreen
from client.widgets.channel_sidebar import ChannelSidebar
from client.widgets.message_view import MessageView


# ── helpers ───────────────────────────────────────────────────────────────────

def _server_msg(payload: dict) -> TraxusApp.ServerMessage:
    return TraxusApp.ServerMessage(payload)


def _line_count(mv: MessageView) -> int:
    """Number of rendered lines currently in the RichLog."""
    return len(mv.lines)


# ── _chat() correctness ───────────────────────────────────────────────────────

class TestChatHelper(unittest.IsolatedAsyncioTestCase):
    """
    _chat() must return the active ChatScreen, or None when another screen is
    active.  This is the exact method that was broken: it previously used
    query_one(ChatScreen), which silently raised NoMatches and caused _chat()
    to return None even when ChatScreen was the visible screen.
    """

    async def test_returns_none_on_login_screen(self):
        app = TraxusApp()
        async with app.run_test():
            self.assertIsInstance(app.screen, LoginScreen)
            self.assertIsNone(app._chat())

    async def test_returns_chat_screen_when_active(self):
        """The central regression test: _chat() must NOT return None on ChatScreen."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            result = app._chat()
            self.assertIsNotNone(
                result,
                "_chat() returned None while ChatScreen was active — "
                "check that self.screen is used instead of query_one(ChatScreen)",
            )
            self.assertIsInstance(result, ChatScreen)

    async def test_returns_none_after_switching_back_to_login(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            await app.switch_screen(LoginScreen())
            await pilot.pause()

            self.assertIsNone(app._chat())


# ── server messages while LoginScreen is active ───────────────────────────────

class TestServerMessagesOnLoginScreen(unittest.IsolatedAsyncioTestCase):
    """
    Messages that arrive before ChatScreen is mounted (e.g., the auto-join
    joined + channel_list burst that comes right after auth_ok) must be
    silently discarded — not crash the app.
    """

    async def test_joined_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            self.assertIsInstance(app.screen, LoginScreen)
            app.post_message(_server_msg({"type": "joined", "channel": "general", "history": []}))
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginScreen)   # still alive

    async def test_channel_list_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            app.post_message(_server_msg({"type": "channel_list", "channels": []}))
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginScreen)

    async def test_chat_message_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            app.post_message(_server_msg({
                "type": "chat",
                "channel": "general",
                "user_id": "u1",
                "username": "alice",
                "content": "hello",
                "ts": 0.0,
            }))
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginScreen)

    async def test_nick_changed_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            app.post_message(_server_msg({
                "type": "nick_changed",
                "old_nick": "alice",
                "new_nick": "alice_dev",
                "user_id": "u1",
            }))
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginScreen)


# ── server messages while ChatScreen is active ────────────────────────────────

class TestServerMessageRouting(unittest.IsolatedAsyncioTestCase):
    """
    When ChatScreen is active, ServerMessage payloads must update the correct
    reactive state and widgets.  These tests would have failed with the old
    query_one() implementation because _chat() would return None and every
    handler body would be skipped.
    """

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_joined_updates_current_channel(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)

            app.post_message(_server_msg({"type": "joined", "channel": "random", "history": []}))
            await pilot.pause()

            self.assertEqual(app.current_channel, "random")

    async def test_joined_appends_system_message(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.post_message(_server_msg({"type": "joined", "channel": "random", "history": []}))
            await pilot.pause()

            self.assertGreater(
                _line_count(mv), before,
                "joined message must append a system line to the MessageView",
            )

    async def test_channel_list_populates_sidebar(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            channels = [
                {"name": "general", "topic": "General", "member_count": 2},
                {"name": "random",  "topic": "Random",  "member_count": 1},
            ]
            app.post_message(_server_msg({"type": "channel_list", "channels": channels}))
            await pilot.pause()

            sidebar = app.screen.query_one("#sidebar", ChannelSidebar)
            items = list(sidebar.query_one("#channel-list").query("ListItem"))
            self.assertEqual(len(items), 2)

    async def test_nick_changed_updates_own_username(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.username = "alice"

            app.post_message(_server_msg({
                "type": "nick_changed",
                "old_nick": "alice",
                "new_nick": "alice_dev",
                "user_id": "u1",
            }))
            await pilot.pause()

            self.assertEqual(app.username, "alice_dev")

    async def test_nick_changed_does_not_update_other_users_nick(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.username = "alice"

            app.post_message(_server_msg({
                "type": "nick_changed",
                "old_nick": "bob",
                "new_nick": "bob_dev",
                "user_id": "u2",
            }))
            await pilot.pause()

            self.assertEqual(app.username, "alice")

    async def test_error_message_appends_to_message_view(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.post_message(_server_msg({"type": "error", "code": "no_such_channel", "message": "nope"}))
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_system_message_appends_to_message_view(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.post_message(_server_msg({
                "type": "system",
                "channel": "general",
                "content": "alice joined #general",
                "ts": 0.0,
            }))
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_chat_message_appends_to_message_view(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.post_message(_server_msg({
                "type": "chat",
                "channel": "general",
                "user_id": "u1",
                "username": "alice",
                "content": "hello everyone",
                "ts": 0.0,
            }))
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)


# ── command dispatch writes to MessageView ────────────────────────────────────

class TestCommandDispatch(unittest.IsolatedAsyncioTestCase):
    """
    Client-only commands (/help, unknown command, missing-arg hints) must
    produce visible output in the MessageView even without a server response.
    """

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_help_writes_output(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/help")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_unknown_command_writes_error(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/xyzzy")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_join_missing_arg_writes_hint(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/join")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_nick_missing_arg_writes_hint(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/nick")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_create_missing_arg_writes_hint(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/create")
            await pilot.pause()

            self.assertGreater(_line_count(mv), before)

    async def test_command_dispatch_does_not_crash_on_login_screen(self):
        """_local() must not raise when _chat() returns None."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            self.assertIsInstance(app.screen, LoginScreen)
            # These would crash if _local() didn't guard on _chat() being None
            app.handle_input("/xyzzy")
            app.handle_input("/join")
            app.handle_input("/nick")
            await pilot.pause()
            self.assertIsInstance(app.screen, LoginScreen)


# ── AudioFrame dispatch ───────────────────────────────────────────────────────

class TestAudioFrameDispatch(unittest.IsolatedAsyncioTestCase):
    """
    AudioFrame messages should dispatch to audio_engine.play() via
    on_traxus_app_audio_frame. We mock AudioEngine to verify the call.
    """

    async def test_audio_frame_dispatches_to_play(self):
        from unittest.mock import MagicMock, patch
        from shared import voice_protocol

        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            played_chunks: list[bytes] = []

            def fake_play(pcm_bytes: bytes) -> None:
                played_chunks.append(pcm_bytes)

            app._audio_engine.play = fake_play  # type: ignore[method-assign]

            # Build a valid S2C frame
            pcm = b"\x01\x02\x03\x04"
            ch = b"lounge"
            un = b"alice"
            frame = bytes([len(ch)]) + ch + bytes([len(un)]) + un + pcm

            app.post_message(TraxusApp.AudioFrame(frame))
            await pilot.pause()

            self.assertEqual(len(played_chunks), 1)
            self.assertEqual(played_chunks[0], pcm)

    async def test_malformed_audio_frame_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app.post_message(TraxusApp.AudioFrame(b"\xff"))  # malformed
            await pilot.pause()
            # Should not crash — still on ChatScreen
            self.assertIsInstance(app.screen, ChatScreen)


# ── F9 PTT binding ────────────────────────────────────────────────────────────

class TestPttF9Binding(unittest.IsolatedAsyncioTestCase):
    """
    F9 must trigger toggle_ptt() regardless of which widget is focused.

    The binding is declared on TraxusApp with priority=True, which means
    Textual checks it before dispatching the key to the focused Input widget.
    These tests prove that priority=True wiring actually works end-to-end.
    """

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_f9_sets_transmitting_true_when_in_voice_channel(self):
        """First F9 press while in a voice channel enables PTT."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"

            with patch("client.app.AUDIO_AVAILABLE", True):
                app._audio_engine.start = MagicMock()
                # capture_loop must exit immediately so the worker doesn't hang
                async def _noop_capture(channel, send_fn):
                    return
                app._audio_engine.capture_loop = _noop_capture

                await pilot.press("f9")
                await pilot.pause()

            self.assertTrue(
                app._audio_engine.transmitting,
                "F9 must set transmitting=True (PTT on); "
                "if this fails, priority=True is missing or not working",
            )

    async def test_f9_sets_transmitting_false_on_second_press(self):
        """Second F9 press while transmitting disables PTT."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"

            with patch("client.app.AUDIO_AVAILABLE", True):
                app._audio_engine.start = MagicMock()
                app._audio_engine.stop = MagicMock()

                async def _noop_capture(channel, send_fn):
                    return
                app._audio_engine.capture_loop = _noop_capture

                await pilot.press("f9")
                await pilot.pause()
                await pilot.press("f9")
                await pilot.pause()

            self.assertFalse(app._audio_engine.transmitting)

    async def test_f9_updates_status_bar_ptt_indicator(self):
        """F9 must update the PTT indicator in the status bar."""
        from unittest.mock import patch, MagicMock
        from client.widgets.status_bar import StatusBar

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"

            with patch("client.app.AUDIO_AVAILABLE", True):
                app._audio_engine.start = MagicMock()
                async def _noop_capture(channel, send_fn):
                    return
                app._audio_engine.capture_loop = _noop_capture

                await pilot.press("f9")
                await pilot.pause()

            sb = app.screen.query_one("#status-bar", StatusBar)
            self.assertTrue(
                sb.ptt_active,
                "Status bar must show PTT active after F9",
            )

    async def test_f9_without_voice_channel_shows_error_not_crash(self):
        """F9 when not in a voice channel must show an error message, not crash."""
        from unittest.mock import patch

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            # current_voice_channel is "" by default
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            with patch("client.app.AUDIO_AVAILABLE", True):
                await pilot.press("f9")
                await pilot.pause()

            self.assertGreater(
                _line_count(mv), before,
                "F9 without a voice channel must print an error to the message view",
            )
            self.assertFalse(app._audio_engine.transmitting)

    async def test_f9_fires_even_when_input_is_focused(self):
        """
        The Input widget normally absorbs all key events.
        priority=True on the binding must bypass this.
        """
        from unittest.mock import patch, MagicMock
        from textual.widgets import Input

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"

            # Explicitly focus the Input widget (this is the normal state during chat)
            app.screen.query_one("#message-input", Input).focus()
            await pilot.pause()

            with patch("client.app.AUDIO_AVAILABLE", True):
                app._audio_engine.start = MagicMock()
                async def _noop_capture(channel, send_fn):
                    return
                app._audio_engine.capture_loop = _noop_capture

                await pilot.press("f9")
                await pilot.pause()

            self.assertTrue(
                app._audio_engine.transmitting,
                "F9 must fire even when the Input widget has focus; "
                "priority=True binding is required for this to work",
            )


if __name__ == "__main__":
    unittest.main()
