"""
Tests for PTT hold mode (toggle vs hold behaviour).

Covers:
  - Toggle mode regression: two presses flip state on/off
  - Hold+mouse: MouseDown starts, MouseUp stops
  - Hold+keyboard: key press starts; debounce fires after 300 ms to stop
  - Hold+keyboard: repeated key events reset the debounce timer
  - Settings persistence: ptt_mode round-trips; missing key defaults to "toggle"
"""
import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual import events

from client.app import TraxusApp, PTT_HOLD_DEBOUNCE_MS
from client.screens.chat_screen import ChatScreen


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_mouse_down(button: int) -> events.MouseDown:
    return events.MouseDown(widget=None, x=0, y=0, delta_x=0, delta_y=0,
                            button=button, shift=False, meta=False, ctrl=False)


def _make_mouse_up(button: int) -> events.MouseUp:
    return events.MouseUp(widget=None, x=0, y=0, delta_x=0, delta_y=0,
                          button=button, shift=False, meta=False, ctrl=False)


async def _setup_voice(app, pilot):
    """Switch to ChatScreen and configure app for voice."""
    await app.switch_screen(ChatScreen())
    await pilot.pause()
    app.current_voice_channel = "lounge"
    app._audio_engine.start = MagicMock()
    app._audio_engine.stop = MagicMock()


# ── Toggle mode regression ────────────────────────────────────────────────────

class TestToggleModeRegression(unittest.IsolatedAsyncioTestCase):
    """Toggle mode must behave exactly as before: two presses flip PTT on/off."""

    async def test_toggle_mode_first_press_starts_transmitting(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "f9"
            app._ptt_mode = "toggle"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                await pilot.press("f9")
                await pilot.pause()

            self.assertTrue(app._transmitting)

    async def test_toggle_mode_second_press_stops_transmitting(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "f9"
            app._ptt_mode = "toggle"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                await pilot.press("f9")
                await pilot.pause()
                await pilot.press("f9")
                await pilot.pause()

            self.assertFalse(app._transmitting)


# ── Hold mode — mouse ─────────────────────────────────────────────────────────

class TestHoldModeMouse(unittest.IsolatedAsyncioTestCase):

    async def test_mouse_down_starts_transmitting_in_hold_mode(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "mouse3"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app.on_mouse_down(_make_mouse_down(3))
                await pilot.pause()

            self.assertTrue(app._transmitting)

    async def test_mouse_up_stops_transmitting_in_hold_mode(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "mouse3"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app.on_mouse_down(_make_mouse_down(3))
                await pilot.pause()
                self.assertTrue(app._transmitting)

                app.on_mouse_up(_make_mouse_up(3))
                await pilot.pause()

            self.assertFalse(app._transmitting)

    async def test_mouse_up_wrong_button_does_not_stop(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "mouse3"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app.on_mouse_down(_make_mouse_down(3))
                await pilot.pause()
                app.on_mouse_up(_make_mouse_up(1))  # wrong button
                await pilot.pause()

            self.assertTrue(app._transmitting)

    async def test_toggle_mode_mouse_up_has_no_effect(self):
        """MouseUp in toggle mode must not stop PTT."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "mouse3"
            app._ptt_mode = "toggle"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app.on_mouse_down(_make_mouse_down(3))
                await pilot.pause()
                app.on_mouse_up(_make_mouse_up(3))
                await pilot.pause()

            self.assertTrue(app._transmitting)


# ── Hold mode — keyboard debounce ─────────────────────────────────────────────

class TestHoldModeKeyboard(unittest.IsolatedAsyncioTestCase):

    async def test_key_press_starts_transmitting_in_hold_mode(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "f9"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                await pilot.press("f9")
                await pilot.pause()

            self.assertTrue(app._transmitting)

    async def test_debounce_stops_transmitting_after_timeout(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "f9"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                # First press starts PTT (no debounce armed yet)
                await pilot.press("f9")
                await pilot.pause()
                self.assertTrue(app._transmitting)

                # Second press (simulates key-repeat) arms the debounce
                await pilot.press("f9")
                await pilot.pause()

                # Wait longer than the debounce timeout without more key events
                await asyncio.sleep((PTT_HOLD_DEBOUNCE_MS + 100) / 1000)
                await pilot.pause()

            self.assertFalse(app._transmitting)

    async def test_repeated_key_events_reset_debounce(self):
        """Key-repeat events within the debounce window keep PTT active."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_key = "f9"
            app._ptt_mode = "hold"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                await pilot.press("f9")
                await pilot.pause()

                # Send two more key presses within the debounce window
                interval = (PTT_HOLD_DEBOUNCE_MS - 50) / 1000
                await asyncio.sleep(interval)
                await pilot.press("f9")
                await asyncio.sleep(interval)
                await pilot.press("f9")
                await pilot.pause()

                # Still transmitting — debounce was reset each time
                self.assertTrue(app._transmitting)


# ── Settings persistence ──────────────────────────────────────────────────────

class TestPttModeSettingsPersistence(unittest.IsolatedAsyncioTestCase):

    def test_ptt_mode_default_is_toggle(self):
        import tempfile
        from pathlib import Path
        from client import settings as s_mod

        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "nonexistent.json"  # file does not exist
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                settings = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original

        self.assertEqual(settings.get("ptt_mode", "toggle"), "toggle")

    def test_ptt_mode_round_trips(self):
        import json
        import tempfile
        from pathlib import Path
        from client import settings as s_mod

        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "settings.json"
            fake_file.write_text(
                json.dumps({"ptt_key": "f9", "ptt_mode": "hold"}), encoding="utf-8"
            )
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original

        self.assertEqual(loaded["ptt_mode"], "hold")

    def test_missing_ptt_mode_key_defaults_to_toggle(self):
        import json
        import tempfile
        from pathlib import Path
        from client import settings as s_mod

        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "settings.json"
            fake_file.write_text(
                json.dumps({"ptt_key": "f9"}), encoding="utf-8"  # no ptt_mode
            )
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original

        self.assertEqual(loaded["ptt_mode"], "toggle")


if __name__ == "__main__":
    unittest.main()
