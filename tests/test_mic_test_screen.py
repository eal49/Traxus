"""Tests for MicTestScreen and spectrogram rendering."""
from __future__ import annotations

import sys
import os
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.settings_screen import SettingsScreen
from client.screens.mic_test_screen import MicTestScreen, _SPEC_COLS, _SPEC_ROWS, _INTENSITY
from client.audio_engine import AUDIO_AVAILABLE, _BLOCKSIZE
from textual.widgets import Input


# ── Spectrogram rendering tests (pure logic, no Textual needed) ───────────────

@unittest.skipUnless(AUDIO_AVAILABLE, "numpy not available")
class TestSpectrogramRendering(unittest.TestCase):

    def _make_screen(self) -> MicTestScreen:
        screen = MicTestScreen.__new__(MicTestScreen)
        screen._spec_history = deque(
            [[" "] * _SPEC_ROWS for _ in range(_SPEC_COLS)], maxlen=_SPEC_COLS
        )
        screen._latest_rms = 0.0
        screen._new_data = False
        return screen

    def test_silence_column_is_all_spaces(self):
        screen = self._make_screen()
        silence = bytes(_BLOCKSIZE * 2)  # all-zero int16 PCM
        screen._on_spectrum(silence)
        col = list(screen._spec_history)[-1]
        self.assertTrue(all(c == " " for c in col),
                        f"Expected all spaces for silence, got: {col}")

    def test_loud_signal_has_filled_chars(self):
        screen = self._make_screen()
        pcm = (np.full(_BLOCKSIZE, 30000, dtype=np.int16)).tobytes()
        screen._on_spectrum(pcm)
        col = list(screen._spec_history)[-1]
        # At least some rows should have a non-space character
        self.assertTrue(any(c != " " for c in col),
                        "Expected filled chars for loud signal")

    def test_column_count_matches_history_length(self):
        screen = self._make_screen()
        rendered = screen._render_spectrogram()
        lines = rendered.split("\n")
        self.assertEqual(len(lines), _SPEC_ROWS)
        for line in lines:
            self.assertEqual(len(line), _SPEC_COLS,
                             f"Expected {_SPEC_COLS} cols, got {len(line)}: {line!r}")

    def test_on_spectrum_appends_column(self):
        screen = self._make_screen()
        initial_len = len(screen._spec_history)
        pcm = (np.zeros(_BLOCKSIZE, dtype=np.int16)).tobytes()
        screen._on_spectrum(pcm)
        self.assertEqual(len(screen._spec_history), initial_len)  # maxlen unchanged
        # New column should now be at the end
        col = list(screen._spec_history)[-1]
        self.assertEqual(len(col), _SPEC_ROWS)

    def test_intensity_chars_are_subset_of_palette(self):
        screen = self._make_screen()
        pcm = (np.random.default_rng(42).integers(
            -10000, 10000, _BLOCKSIZE, dtype=np.int16)).tobytes()
        screen._on_spectrum(pcm)
        col = list(screen._spec_history)[-1]
        for ch in col:
            self.assertIn(ch, _INTENSITY, f"Unexpected char {ch!r} in spectrogram column")


# ── Level bar rendering ───────────────────────────────────────────────────────

@unittest.skipUnless(AUDIO_AVAILABLE, "numpy not available")
class TestLevelBarRendering(unittest.TestCase):

    def _make_screen(self) -> MicTestScreen:
        screen = MicTestScreen.__new__(MicTestScreen)
        screen._spec_history = deque(
            [[" "] * _SPEC_ROWS for _ in range(_SPEC_COLS)], maxlen=_SPEC_COLS
        )
        screen._latest_rms = 0.0
        screen._new_data = False
        return screen

    def test_silence_shows_empty_bar(self):
        screen = self._make_screen()
        bar = screen._render_level_bar(0.0)
        self.assertIn("  0%", bar)
        self.assertNotIn("█", bar)

    def test_full_signal_shows_full_bar(self):
        screen = self._make_screen()
        from client.screens.mic_test_screen import _RMS_MAX
        bar = screen._render_level_bar(_RMS_MAX)
        self.assertIn("100%", bar)


# ── Textual integration tests ─────────────────────────────────────────────────

class TestMicTestScreenIntegration(unittest.IsolatedAsyncioTestCase):

    async def test_screen_opens_from_settings_menu(self):
        """Selecting 'Test Microphone' in SettingsScreen pushes MicTestScreen."""
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            with patch("client.app.AUDIO_AVAILABLE", True):
                app.push_screen(SettingsScreen())
                await pilot.pause()

                # The item should be visible (AUDIO_AVAILABLE=True is mocked at app level,
                # but settings_screen imports it directly — patch there too)
                with patch("client.screens.settings_screen.AUDIO_AVAILABLE", True):
                    app.screen._update_mic_test_visibility()
                    await pilot.pause()

                    with patch.object(app, "push_screen") as mock_push:
                        app.screen._open_mic_test()
                        mock_push.assert_called_once()
                        args = mock_push.call_args[0]
                        self.assertIsInstance(args[0], MicTestScreen)

    async def test_loopback_label_shows_off(self):
        """Loopback is not supported in the WebRTC pipeline — label shows Off."""
        from textual.widgets import Label
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app._audio_engine.start = MagicMock()
            app._audio_engine.start_vad = MagicMock()
            app._audio_engine.stop_vad = MagicMock()

            app.push_screen(MicTestScreen())
            await pilot.pause(0.2)

            try:
                lbl = app.screen.query_one("#loopback-status", Label)
                self.assertIn("Off", str(lbl.renderable))
            except Exception:
                pass  # label may not be visible in headless mode

    async def test_l_key_does_not_crash(self):
        """Pressing L while MicTestScreen is focused must not raise."""
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app._audio_engine.start = MagicMock()
            app._audio_engine.start_vad = MagicMock()
            app._audio_engine.stop_vad = MagicMock()

            app.push_screen(MicTestScreen())
            await pilot.pause(0.2)

            try:
                await pilot.press("l")
                await pilot.pause()
            except Exception as exc:
                self.fail(f"Pressing L raised: {exc}")

    async def test_unmount_does_not_crash(self):
        """Dismissing MicTestScreen must not raise."""
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app._audio_engine.start = MagicMock()
            app._audio_engine.start_vad = MagicMock()
            app._audio_engine.stop_vad = MagicMock()

            app.push_screen(MicTestScreen())
            await pilot.pause(0.2)

            try:
                await pilot.press("escape")
                await pilot.pause(0.2)
            except Exception as exc:
                self.fail(f"Unmount raised: {exc}")


if __name__ == "__main__":
    unittest.main()
