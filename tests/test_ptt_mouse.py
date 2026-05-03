"""
Tests for mouse button PTT binding.

Covers:
  - TraxusApp.on_mouse_down toggles PTT when _ptt_key = "mouse3"
  - Non-matching button does not toggle PTT
  - Keyboard key still works when _ptt_key = "f9" (regression)
  - PttKeyScreen dismisses with "mouse3" when a MouseDown button=3 event fires
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual import events

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.settings_screen import PttKeyScreen


def _mouse_event(button: int) -> events.MouseDown:
    """Build a minimal MouseDown event for the given button number."""
    return events.MouseDown(
        widget=None, x=0, y=0, delta_x=0, delta_y=0,
        button=button, shift=False, meta=False, ctrl=False,
    )


# ── TraxusApp mouse PTT handler ───────────────────────────────────────────────

class TestMousePttHandler(unittest.IsolatedAsyncioTestCase):
    """on_mouse_down must toggle PTT when _ptt_key is a mouse button string."""

    async def _on_chat(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()
        app._ptt_mode = "toggle"

    async def test_mouse3_toggles_ptt(self):
        """MouseDown button=3 toggles PTT when _ptt_key = 'mouse3'."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._ptt_key = "mouse3"
            app.current_voice_channel = "lounge"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._audio_engine.start = MagicMock()

                app.on_mouse_down(_mouse_event(3))
                await pilot.pause()

            self.assertTrue(
                app._transmitting,
                "mouse3 down must enable PTT when _ptt_key = 'mouse3'",
            )

    async def test_non_matching_button_does_not_toggle(self):
        """MouseDown button=1 must NOT toggle PTT when _ptt_key = 'mouse3'."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._ptt_key = "mouse3"
            app.current_voice_channel = "lounge"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._audio_engine.start = MagicMock()

                app.on_mouse_down(_mouse_event(1))
                await pilot.pause()

            self.assertFalse(
                app._transmitting,
                "mouse1 must not trigger PTT when _ptt_key = 'mouse3'",
            )

    async def test_keyboard_still_works_as_regression(self):
        """F9 keyboard still toggles PTT when _ptt_key = 'f9' (regression)."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._ptt_key = "f9"
            app.current_voice_channel = "lounge"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._audio_engine.start = MagicMock()

                await pilot.press("f9")
                await pilot.pause()

            self.assertTrue(
                app._transmitting,
                "F9 must still toggle PTT when _ptt_key = 'f9'",
            )

    async def test_mouse_handler_does_not_fire_for_keyboard_ptt_key(self):
        """on_mouse_down must not toggle PTT when _ptt_key is a keyboard key."""
        from unittest.mock import patch, MagicMock

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._on_chat(app, pilot)
            app._ptt_key = "f9"
            app.current_voice_channel = "lounge"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._audio_engine.start = MagicMock()

                app.on_mouse_down(_mouse_event(3))
                await pilot.pause()

            self.assertFalse(
                app._transmitting,
                "mouse click must not trigger PTT when _ptt_key is a keyboard key",
            )


# ── PttKeyScreen mouse capture ────────────────────────────────────────────────

class TestPttKeyScreenMouseCapture(unittest.IsolatedAsyncioTestCase):
    """PttKeyScreen must dismiss with 'mouseN' on mouse button click."""

    async def test_mouse_down_dismisses_with_mouse_string(self):
        """MouseDown button=3 on PttKeyScreen must dismiss with 'mouse3'."""
        results: list[str | None] = []

        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.push_screen(PttKeyScreen("f9"), results.append)
            await pilot.pause()

            screen = app.screen
            self.assertIsInstance(screen, PttKeyScreen)
            screen.on_mouse_down(_mouse_event(3))
            await pilot.pause()

        self.assertEqual(results, ["mouse3"],
                         "PttKeyScreen must dismiss with 'mouse3' on button=3 click")

    async def test_escape_still_cancels(self):
        """Escape must still dismiss PttKeyScreen with None."""
        results: list[str | None] = []

        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.push_screen(PttKeyScreen("f9"), results.append)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

        self.assertEqual(results, [None],
                         "Escape must dismiss PttKeyScreen with None")


if __name__ == "__main__":
    unittest.main()
