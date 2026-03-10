"""
End-to-end PTT integration test.

Starts a real Traxus server subprocess, drives the full TUI client flow via
Textual's test pilot, creates a voice channel, joins it, presses F9, and
asserts that PTT activates (transmitting=True, status bar shows ● MIC).

sounddevice.InputStream is mocked to avoid needing real audio hardware.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual.widgets import Input

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.login_screen import LoginScreen
from client.widgets.status_bar import StatusBar


class TestPttEndToEnd(unittest.IsolatedAsyncioTestCase):
    """Full integration: server subprocess + TUI client + voice channel + F9."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)  # let the server bind its port

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        cls._server.wait(timeout=5)

    async def test_f9_activates_ptt_after_vjoin(self) -> None:
        """
        Full flow:
          login → vcreate lounge → vjoin lounge → F9 → assert PTT on
        """
        app = TraxusApp()

        # Prevent sounddevice from opening a real microphone stream.
        # capture_loop is replaced with a no-op so the worker exits immediately.
        app_start_mock = MagicMock()

        async def _noop_capture(channel, send_fn):
            return

        async with app.run_test(size=(120, 40)) as pilot:

            # ── 1. Login screen ───────────────────────────────────────────────
            self.assertIsInstance(app.screen, LoginScreen)

            server_input = app.screen.query_one("#server-input", Input)
            server_input.value = "ws://localhost:8765"
            nick_input = app.screen.query_one("#nick-input", Input)
            nick_input.value = "pttbot"
            nick_input.focus()
            await pilot.press("enter")   # triggers _try_connect

            # Wait for WS auth → ChatScreen switch (up to 3 s)
            for _ in range(20):
                await pilot.pause(0.15)
                if isinstance(app.screen, ChatScreen):
                    break
            self.assertIsInstance(
                app.screen, ChatScreen,
                "Did not reach ChatScreen — server may not be running or auth failed",
            )

            # Patch AUDIO_AVAILABLE=True for the rest of the test.
            # sounddevice may not be installed in the test's Python environment;
            # without this patch, /vjoin and F9 both bail out early with
            # "Voice not available" and nothing is sent to the server.
            with patch("client.app.AUDIO_AVAILABLE", True):

                # ── 2. Create voice channel ───────────────────────────────────
                app.handle_input("/vcreate lounge")
                await pilot.pause(0.5)

                # ── 3. Join voice channel ─────────────────────────────────────
                app._audio_engine.start = app_start_mock
                app._audio_engine.capture_loop = _noop_capture

                app.handle_input("/vjoin lounge")

                # Wait for voice_state → current_voice_channel populated (up to 4 s)
                for _ in range(40):
                    await pilot.pause(0.1)
                    if app.current_voice_channel:
                        break

                self.assertEqual(
                    app.current_voice_channel,
                    "lounge",
                    f"voice_state not received — current_voice_channel={app.current_voice_channel!r}; "
                    "check that /vjoin sends voice_join and server returns voice_state",
                )

                # ── 4. Press F9 ───────────────────────────────────────────────
                # Ensure _ptt_key is "f9" regardless of the system settings file.
                app._ptt_key = "f9"
                # Give the Input widget focus — normal chat state — to prove
                # the on_key handler fires despite Input absorbing keys.
                app.screen.query_one("#message-input", Input).focus()
                await pilot.pause(0.1)
                await pilot.press("f9")
                await pilot.pause(0.3)

                # ── 5. Assertions ─────────────────────────────────────────────
                self.assertTrue(
                    app._audio_engine.transmitting,
                    "app._audio_engine.transmitting must be True after F9 — "
                    "priority=True binding or action_ptt_toggle wiring is broken",
                )

                sb = app.screen.query_one("#status-bar", StatusBar)
                self.assertTrue(
                    sb._ptt_active,
                    "StatusBar.ptt_active must be True after F9 — "
                    "toggle_ptt() must call chat.update_ptt(True)",
                )

                app_start_mock.assert_called_once()   # AudioEngine.start() was called

                # ── 6. F9 again turns PTT off ─────────────────────────────────
                app._audio_engine.stop = MagicMock()
                await pilot.press("f9")
                await pilot.pause(0.3)

                self.assertFalse(app._audio_engine.transmitting, "Second F9 must turn PTT off")
                self.assertFalse(sb._ptt_active, "Status bar must clear ● MIC after PTT off")


if __name__ == "__main__":
    unittest.main()
