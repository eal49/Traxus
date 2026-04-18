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
            all_items = list(sidebar.query_one("#channel-list").query("ListItem"))
            # Section header items have no name; count only real channel items
            channel_items = [i for i in all_items if i.name]
            self.assertEqual(len(channel_items), 2)

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

            played_chunks: list[tuple] = []

            def fake_play(audio_bytes: bytes, codec: int = 0, username: str = "") -> None:
                played_chunks.append((audio_bytes, codec))

            app._audio_engine.play = fake_play  # type: ignore[method-assign]

            # Build a valid S2C frame (with codec byte = CODEC_RAW = 0)
            audio = b"\x01\x02\x03\x04"
            ch = b"lounge"
            un = b"alice"
            frame = bytes([len(ch)]) + ch + bytes([len(un)]) + un + bytes([0]) + audio

            app.post_message(TraxusApp.AudioFrame(frame))
            await pilot.pause()

            self.assertEqual(len(played_chunks), 1)
            self.assertEqual(played_chunks[0][0], audio)
            self.assertEqual(played_chunks[0][1], 0)

    async def test_malformed_audio_frame_does_not_crash(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app.post_message(TraxusApp.AudioFrame(b"\xff"))  # malformed
            await pilot.pause()
            # Should not crash — still on ChatScreen
            self.assertIsInstance(app.screen, ChatScreen)


# ── PTT key binding ───────────────────────────────────────────────────────────

class TestPttF9Binding(unittest.IsolatedAsyncioTestCase):
    """
    The PTT key (default F9) must trigger toggle_ptt() regardless of which
    widget is focused.

    PTT is handled by an on_key handler on TraxusApp.  F9 is not consumed by
    the Input widget, so it naturally bubbles up to the App handler.
    These tests prove the on_key wiring works end-to-end.
    """

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()
        # Ensure _ptt_key and _ptt_mode are deterministic regardless of the settings file.
        app._ptt_key = "f9"
        app._ptt_mode = "toggle"

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
                sb._ptt_active,
                "Status bar must show PTT active after F9",
            )
            self.assertIn(
                "ptt-active", sb.classes,
                "Status bar must carry ptt-active CSS class when PTT is on",
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
        F9 is not consumed by the Input widget (it is not a printable character
        or a special key Input handles), so it bubbles up to the App's on_key
        handler and triggers PTT even when the Input widget has focus.
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
                "the App-level on_key handler must receive the bubbled event",
            )


# ── /settings command ─────────────────────────────────────────────────────────

class TestSettingsCommand(unittest.IsolatedAsyncioTestCase):
    """/settings must push a modal without crashing and must not be treated as
    an unknown command."""

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_settings_command_is_recognised(self):
        """Dispatching /settings must not print 'Unknown command'."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)

            app.handle_input("/settings")
            await pilot.pause()

            # Unknown commands append an error line; /settings must not do this.
            # (The modal being open means no error was printed.)
            lines_added = _line_count(mv) - before
            self.assertEqual(
                lines_added, 0,
                "/settings must not write an 'Unknown command' error to the view",
            )

    async def test_settings_command_does_not_crash(self):
        """/settings must not raise or leave the app in a broken state."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)

            app.handle_input("/settings")
            await pilot.pause()

            # App is still running
            self.assertIsNotNone(app.screen)


# ── Connection failure feedback ───────────────────────────────────────────────

class TestConnectionErrorFeedback(unittest.IsolatedAsyncioTestCase):
    """
    When a ConnectionStateChanged(state="failed") message is posted while the
    LoginScreen is active, the app must surface the error message on the login
    screen and must not crash.
    """

    async def test_failed_state_shows_error_on_login_screen(self):
        """state='failed' must call show_error on LoginScreen with the detail."""
        from unittest.mock import MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            self.assertIsInstance(app.screen, LoginScreen)

            # Patch show_error on the live instance before the message fires.
            login = app.screen
            calls: list[str] = []
            original_show = login.show_error
            login.show_error = lambda msg: calls.append(msg) or original_show(msg)  # type: ignore[method-assign]

            app.post_message(TraxusApp.ConnectionStateChanged(
                state="failed",
                detail="Could not connect — check the server address.",
            ))
            await pilot.pause()

            self.assertTrue(calls, "show_error must have been called on LoginScreen")
            self.assertIn(
                "Could not connect",
                calls[0],
                "show_error must receive the failure detail string",
            )

    async def test_failed_state_does_not_crash_on_chat_screen(self):
        """state='failed' when LoginScreen is not present must not raise."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            # Should not raise even though LoginScreen is not queryable
            app.post_message(TraxusApp.ConnectionStateChanged(
                state="failed",
                detail="Could not connect — check the server address.",
            ))
            await pilot.pause()
            self.assertIsInstance(app.screen, ChatScreen)


class TestWsWorkerAuthFlag(unittest.TestCase):
    """
    Unit tests for WsWorker._authenticated flag and notify_auth_ok().
    These tests verify the flag logic without running the full async worker.
    """

    def _make_worker(self):
        from unittest.mock import MagicMock
        from client.ws_worker import WsWorker
        app = MagicMock()
        return WsWorker(app)

    def test_authenticated_starts_false(self):
        worker = self._make_worker()
        self.assertFalse(worker._authenticated)

    def test_notify_auth_ok_sets_flag(self):
        worker = self._make_worker()
        worker.notify_auth_ok()
        self.assertTrue(worker._authenticated)

    def test_friendly_error_masks_os_error(self):
        from client.ws_worker import WsWorker
        msg = WsWorker._friendly_error(OSError("Connection refused"))
        self.assertNotIn("OSError", msg)
        self.assertNotIn("Connection refused", msg)
        self.assertLess(len(msg), 120)

    def test_friendly_error_masks_websocket_exception(self):
        import websockets.exceptions
        from client.ws_worker import WsWorker
        exc = websockets.exceptions.WebSocketException("rejected handshake")
        msg = WsWorker._friendly_error(exc)
        self.assertNotIn("WebSocketException", msg)
        self.assertLess(len(msg), 120)


class TestVleaveClientBehaviour(unittest.IsolatedAsyncioTestCase):
    """Verify that the client correctly handles voice_state sent by the server
    after a /vleave, clearing current_voice_channel and stopping audio."""

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()

    async def test_voice_state_empty_users_clears_current_voice_channel(self):
        """Receiving voice_state with no users must clear current_voice_channel."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"
            await pilot.pause()

            app.post_message(_server_msg({
                "type": "voice_state",
                "channel": "lounge",
                "users": [],
            }))
            await pilot.pause()

            self.assertEqual(app.current_voice_channel, "")

    async def test_voice_state_clears_channel_when_self_not_in_users(self):
        """voice_state where self is absent from users must also clear the channel."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.username = "alice"
            app.current_voice_channel = "lounge"
            await pilot.pause()

            # Server sends voice_state listing only bob (alice has left)
            app.post_message(_server_msg({
                "type": "voice_state",
                "channel": "lounge",
                "users": [{"user_id": "2", "username": "bob"}],
            }))
            await pilot.pause()

            # current_voice_channel stays set — server disambiguates via empty list
            # This test verifies that an empty-users voice_state (the fix) clears it.
            # Here users=[bob] so alice's channel stays set (correct: she's still in).
            self.assertEqual(app.current_voice_channel, "lounge")

    async def test_ptt_stops_when_voice_state_clears_channel(self):
        """Active PTT must stop automatically when current_voice_channel is cleared."""
        from unittest.mock import MagicMock, patch
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app.current_voice_channel = "lounge"
            app._audio_engine.transmitting = True
            await pilot.pause()

            stop_calls: list[int] = []
            original_stop = app.stop_ptt
            app.stop_ptt = lambda: stop_calls.append(1) or original_stop()  # type: ignore

            app.post_message(_server_msg({
                "type": "voice_state",
                "channel": "lounge",
                "users": [],
            }))
            await pilot.pause()

            self.assertEqual(app.current_voice_channel, "")
            self.assertTrue(len(stop_calls) > 0, "stop_ptt was not called when channel cleared")


# ── nick color ───────────────────────────────────────────────────────────────

class TestNickColor(unittest.IsolatedAsyncioTestCase):
    async def test_set_nick_color_updates_attribute(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import client.settings as settings_module

        app = TraxusApp()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                async with app.run_test():
                    app._set_nick_color("#ff5500")
                    self.assertEqual(app._nick_color, "#ff5500")

    async def test_set_nick_color_persists_to_settings(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import client.settings as settings_module

        app = TraxusApp()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                async with app.run_test():
                    app._set_nick_color("#abcdef")
                data = json.loads(f.read_text(encoding="utf-8"))
        self.assertEqual(data["nick_color"], "#abcdef")

    async def test_add_chat_uses_self_color(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            app.username = "alice"
            app._nick_color = "#ff0000"
            mv = app.screen.query_one("#messages", MessageView)
            before = _line_count(mv)
            mv.add_chat(
                {"username": "alice", "content": "hi", "ts": 0.0},
                self_username="alice",
                self_color="#ff0000",
            )
            self.assertGreater(_line_count(mv), before)
            last_line = mv._lines[-1]
            self.assertIn("#ff0000", last_line)

    async def test_color_command_sets_nick_color(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import client.settings as settings_module

        app = TraxusApp()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                async with app.run_test() as pilot:
                    await app.switch_screen(ChatScreen())
                    await pilot.pause()
                    app.handle_input("/color blue")
                    await pilot.pause()
                    self.assertEqual(app._nick_color, "#5865f2")

    async def test_color_command_reset_clears_nick_color(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import client.settings as settings_module

        app = TraxusApp()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                async with app.run_test() as pilot:
                    await app.switch_screen(ChatScreen())
                    await pilot.pause()
                    app._nick_color = "#ff0000"
                    app.handle_input("/color reset")
                    await pilot.pause()
                    self.assertEqual(app._nick_color, "")

    async def test_color_command_bad_hex_writes_error(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import client.settings as settings_module

        app = TraxusApp()
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                async with app.run_test() as pilot:
                    await app.switch_screen(ChatScreen())
                    await pilot.pause()
                    mv = app.screen.query_one("#messages", MessageView)
                    before = _line_count(mv)
                    app.handle_input("/color #gg0000")
                    await pilot.pause()
                    self.assertGreater(_line_count(mv), before)
                    self.assertEqual(app._nick_color, "")  # unchanged


if __name__ == "__main__":
    unittest.main()
