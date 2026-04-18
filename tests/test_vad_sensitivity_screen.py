"""Tests for client/screens/vad_sensitivity_screen.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.screens.vad_sensitivity_screen import (
    VadSensitivityScreen,
    _BAR_WIDTH,
    _RMS_MAX,
    _SPEC_ROWS,
    _COARSE_STEP,
    _FINE_STEP,
    _MIN_THRESHOLD,
)


# ── Rendering helpers (pure, no Textual) ─────────────────────────────────────

class TestRenderSpectrogram(unittest.TestCase):
    def test_returns_spec_rows_lines(self):
        screen = VadSensitivityScreen(250.0)
        result = screen._render_spectrogram()
        self.assertEqual(len(result.split("\n")), _SPEC_ROWS)


class TestRenderLevelBar(unittest.TestCase):
    def test_marker_at_correct_column(self):
        import re
        screen = VadSensitivityScreen(750.0)  # 50% of _RMS_MAX=1500 → col 20/40
        bar_str = screen._render_level_bar(0.0, 750.0)
        plain = re.sub(r"\[.*?\]", "", bar_str)
        marker_col = plain.index("▲")
        self.assertEqual(marker_col, int(750.0 / _RMS_MAX * _BAR_WIDTH))

    def test_percentage_shown(self):
        screen = VadSensitivityScreen(250.0)
        bar_str = screen._render_level_bar(_RMS_MAX * 0.5, 250.0)
        self.assertIn("50", bar_str)

    def test_zero_rms_produces_marker(self):
        screen = VadSensitivityScreen(250.0)
        bar_str = screen._render_level_bar(0.0, 250.0)
        self.assertIn("▲", bar_str)


class TestRenderStatus(unittest.TestCase):
    def test_voice_detected_when_above_threshold(self):
        screen = VadSensitivityScreen(250.0)
        self.assertIn("Voice detected", screen._render_status(300.0, 250.0))

    def test_silence_when_below_threshold(self):
        screen = VadSensitivityScreen(250.0)
        self.assertIn("Silence", screen._render_status(100.0, 250.0))

    def test_exactly_at_threshold_is_detected(self):
        screen = VadSensitivityScreen(250.0)
        self.assertIn("Voice detected", screen._render_status(250.0, 250.0))


class TestRenderThresholdLabel(unittest.TestCase):
    def test_shows_threshold_value(self):
        screen = VadSensitivityScreen(347.0)
        label = screen._render_threshold_label()
        self.assertIn("347", label)


# ── Threshold navigation logic ────────────────────────────────────────────────

class TestThresholdNavigation(unittest.TestCase):
    def test_right_increases_by_coarse_step(self):
        screen = VadSensitivityScreen(200.0)
        screen._threshold = min(_RMS_MAX, screen._threshold + _COARSE_STEP)
        self.assertAlmostEqual(screen._threshold, 250.0)

    def test_left_decreases_by_coarse_step(self):
        screen = VadSensitivityScreen(200.0)
        screen._threshold = max(_MIN_THRESHOLD, screen._threshold - _COARSE_STEP)
        self.assertAlmostEqual(screen._threshold, 150.0)

    def test_up_increases_by_fine_step(self):
        screen = VadSensitivityScreen(200.0)
        screen._threshold = min(_RMS_MAX, screen._threshold + _FINE_STEP)
        self.assertAlmostEqual(screen._threshold, 210.0)

    def test_down_decreases_by_fine_step(self):
        screen = VadSensitivityScreen(200.0)
        screen._threshold = max(_MIN_THRESHOLD, screen._threshold - _FINE_STEP)
        self.assertAlmostEqual(screen._threshold, 190.0)

    def test_left_clamps_at_min(self):
        screen = VadSensitivityScreen(30.0)
        screen._threshold = max(_MIN_THRESHOLD, screen._threshold - _COARSE_STEP)
        self.assertAlmostEqual(screen._threshold, _MIN_THRESHOLD)

    def test_right_clamps_at_max(self):
        screen = VadSensitivityScreen(_RMS_MAX - 10.0)
        screen._threshold = min(_RMS_MAX, screen._threshold + _COARSE_STEP)
        self.assertAlmostEqual(screen._threshold, _RMS_MAX)

    def test_initial_threshold_clamped(self):
        screen = VadSensitivityScreen(0.0)
        self.assertGreaterEqual(screen._threshold, _MIN_THRESHOLD)

        screen2 = VadSensitivityScreen(99999.0)
        self.assertLessEqual(screen2._threshold, _RMS_MAX)


# ── Dismiss behaviour (Textual pilot) ────────────────────────────────────────

class TestDismissBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_enter_dismisses_with_float(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list = []
            await app.push_screen(VadSensitivityScreen(250.0), result.append)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], float)
            self.assertAlmostEqual(result[0], 250.0)

    async def test_escape_dismisses_with_none(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list = []
            await app.push_screen(VadSensitivityScreen(250.0), result.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(len(result), 1)
            self.assertIsNone(result[0])

    async def test_right_arrow_increases_threshold(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list = []
            await app.push_screen(VadSensitivityScreen(200.0), result.append)
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertAlmostEqual(result[0], 200.0 + _COARSE_STEP)

    async def test_left_arrow_decreases_threshold(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list = []
            await app.push_screen(VadSensitivityScreen(300.0), result.append)
            await pilot.pause()
            await pilot.press("left")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertAlmostEqual(result[0], 300.0 - _COARSE_STEP)


if __name__ == "__main__":
    unittest.main()
