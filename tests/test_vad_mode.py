"""
Tests for VAD (Voice Activity Detection) auto-transmit mode.

Covers:
  - AudioEngine._detect_voice: RMS threshold per sensitivity level
  - AudioEngine.start() idempotency
  - VAD voice onset calls start_ptt() via _on_vad_state(True)
  - VAD hangover: silence after VAD_HANGOVER_MS stops transmitting
  - VAD hangover reset: voice within hangover window keeps PTT active
  - vad_sensitivity default is "high" when missing from settings
"""
import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from client.app import TraxusApp, VAD_HANGOVER_MS, _VAD_SENSITIVITY_THRESHOLDS
from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
from client.screens.chat_screen import ChatScreen


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_audio(rms_target: float, samples: int = 320) -> np.ndarray:
    """Create a mono int16 buffer with approximately the given RMS energy."""
    val = int(rms_target)
    buf = np.full((samples, 1), val, dtype=np.int16)
    return buf


async def _setup_voice(app, pilot):
    await app.switch_screen(ChatScreen())
    await pilot.pause()
    app.current_voice_channel = "lounge"
    app._audio_engine.start = MagicMock()
    app._audio_engine.stop = MagicMock()
    app._audio_engine.stop_vad = MagicMock()


# ── AudioEngine unit tests ─────────────────────────────────────────────────────

class TestDetectVoice(unittest.TestCase):
    """_detect_voice returns True above threshold, False below."""

    def setUp(self):
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice/numpy not available")
        self.engine = AudioEngine()

    def test_above_threshold_returns_true(self):
        self.engine._vad_threshold = 50.0
        buf = _make_audio(80)
        self.assertTrue(self.engine._detect_voice(buf))

    def test_below_threshold_returns_false(self):
        self.engine._vad_threshold = 50.0
        buf = _make_audio(20)
        self.assertFalse(self.engine._detect_voice(buf))

    def test_exactly_at_threshold_returns_true(self):
        self.engine._vad_threshold = 50.0
        buf = _make_audio(50)
        self.assertTrue(self.engine._detect_voice(buf))

    def test_low_sensitivity_threshold(self):
        self.engine._vad_threshold = _VAD_SENSITIVITY_THRESHOLDS["low"]  # 600
        buf = _make_audio(1000)
        self.assertTrue(self.engine._detect_voice(buf))
        buf_quiet = _make_audio(400)
        self.assertFalse(self.engine._detect_voice(buf_quiet))

    def test_very_high_sensitivity_threshold(self):
        self.engine._vad_threshold = _VAD_SENSITIVITY_THRESHOLDS["very_high"]
        buf = _make_audio(150)
        self.assertTrue(self.engine._detect_voice(buf))
        buf_quiet = _make_audio(50)
        self.assertFalse(self.engine._detect_voice(buf_quiet))


class TestAudioEngineStartIdempotent(unittest.TestCase):
    """start() must be a no-op if the stream is already open."""

    def test_double_start_does_not_crash(self):
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice/numpy not available")
        engine = AudioEngine()
        # Replace stream with a sentinel to simulate already-open
        sentinel = object()
        engine._stream = sentinel
        loop = MagicMock()
        engine.start(loop)
        # Stream must remain the same object (not replaced)
        self.assertIs(engine._stream, sentinel)


# ── VAD state machine tests ────────────────────────────────────────────────────

class TestVadOnsetAndHangover(unittest.IsolatedAsyncioTestCase):

    async def test_vad_voice_onset_starts_transmitting(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_mode = "vad"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._on_vad_state(True)
                await pilot.pause()

            self.assertTrue(app._transmitting)

    async def test_vad_hangover_stops_transmitting_after_timeout(self):
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_mode = "vad"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                # Start transmitting via voice onset
                app._on_vad_state(True)
                await pilot.pause()
                self.assertTrue(app._transmitting)

                # Silence arms the hangover
                app._on_vad_state(False)
                await pilot.pause()

                # Wait longer than the hangover
                await asyncio.sleep((VAD_HANGOVER_MS + 100) / 1000)
                await pilot.pause()

            self.assertFalse(app._transmitting)

    async def test_vad_hangover_reset_keeps_transmitting(self):
        """Voice returning within the hangover window cancels the stop."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await _setup_voice(app, pilot)
            app._ptt_mode = "vad"

            with patch("client.app.WEBRTC_AVAILABLE", True):
                app._on_vad_state(True)
                await pilot.pause()

                # Silence arms the hangover
                app._on_vad_state(False)
                await asyncio.sleep((VAD_HANGOVER_MS - 100) / 1000)

                # Voice resumes before hangover fires
                app._on_vad_state(True)
                await pilot.pause()

                # Still transmitting
                self.assertTrue(app._transmitting)


# ── Settings persistence ────────────────────────────────────────────────────

class TestVadSensitivityDefault(unittest.TestCase):

    def test_vad_sensitivity_default_is_high(self):
        import json
        import tempfile
        from pathlib import Path
        from client import settings as s_mod

        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "nonexistent.json"
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original

        self.assertEqual(loaded.get("vad_sensitivity", "high"), "high")

    def test_vad_sensitivity_round_trips(self):
        import json
        import tempfile
        from pathlib import Path
        from client import settings as s_mod

        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "settings.json"
            fake_file.write_text(
                json.dumps({"ptt_key": "f9", "ptt_mode": "vad", "vad_sensitivity": "low"}),
                encoding="utf-8",
            )
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original

        self.assertEqual(loaded["vad_sensitivity"], "low")


# ── _do_restart_vad ───────────────────────────────────────────────────────────

class TestDoRestartVad(unittest.IsolatedAsyncioTestCase):
    """_do_restart_vad restarts the VAD stream asynchronously after calibration."""

    async def _setup(self, app, pilot):
        await app.switch_screen(ChatScreen())
        await pilot.pause()
        app._ptt_mode = "vad"
        app.current_voice_channel = "lounge"

    async def test_restart_calls_stop_then_start_vad(self):
        """_do_restart_vad must stop VAD, then start it with the current threshold."""
        from unittest.mock import AsyncMock, MagicMock, call

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._setup(app, pilot)

            stop_called = []
            start_called = []

            def fake_stop():
                stop_called.append(True)

            def fake_start(loop, threshold, callback):
                start_called.append(threshold)

            app._audio_engine.stop_vad = fake_stop
            app._audio_engine.start_vad = fake_start

            await app._do_restart_vad()

            self.assertEqual(len(stop_called), 1, "stop_vad must be called once")
            self.assertEqual(len(start_called), 1, "start_vad must be called once")
            self.assertGreater(start_called[0], 0, "threshold must be positive")

    async def test_restart_skips_when_not_in_vad_mode(self):
        """_do_restart_vad must be a no-op when PTT mode is not VAD."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._setup(app, pilot)
            app._ptt_mode = "toggle"

            start_called = []
            app._audio_engine.stop_vad = lambda: None
            app._audio_engine.start_vad = lambda loop, t, cb: start_called.append(t)

            await app._do_restart_vad()

            self.assertEqual(start_called, [], "start_vad must not be called in toggle mode")

    async def test_restart_skips_when_not_in_voice_channel(self):
        """_do_restart_vad must be a no-op when not in a voice channel."""
        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._setup(app, pilot)
            app.current_voice_channel = ""

            start_called = []
            app._audio_engine.stop_vad = lambda: None
            app._audio_engine.start_vad = lambda loop, t, cb: start_called.append(t)

            await app._do_restart_vad()

            self.assertEqual(start_called, [], "start_vad must not be called without voice channel")

    async def test_start_vad_failure_posts_local_message(self):
        """When start_vad raises, a local error message must appear."""
        from client.widgets.message_view import MessageView

        app = TraxusApp()
        async with app.run_test() as pilot:
            await self._setup(app, pilot)
            mv = app.screen.query_one("#messages", MessageView)
            before = len(mv.lines)

            app._audio_engine.stop_vad = lambda: None
            app._audio_engine.start_vad = lambda loop, t, cb: (_ for _ in ()).throw(
                RuntimeError("device unavailable")
            )

            await app._do_restart_vad()
            await pilot.pause()

            self.assertGreater(
                len(mv.lines), before,
                "A local error message must appear when start_vad fails",
            )


# ── VadSensitivityScreen cancel restart ──────────────────────────────────────

class TestVadSensitivityCancel(unittest.TestCase):
    """Cancelling VadSensitivityScreen (Escape) must still restart the VAD stream."""

    def _make_screen(self):
        from unittest.mock import MagicMock
        from client.screens.settings_screen import SettingsScreen

        screen = SettingsScreen.__new__(SettingsScreen)
        app_mock = MagicMock()
        app_mock._ptt_mode = "vad"
        app_mock.current_voice_channel = "lounge"
        app_mock._input_device = None
        app_mock._output_device = None
        screen._app = app_mock
        return screen

    def test_cancel_calls_restart_vad_if_active(self):
        """_on_vad_sensitivity_result(None) must still call _restart_vad_if_active."""
        screen = self._make_screen()
        called = []
        screen._restart_vad_if_active = lambda: called.append(True)

        screen._on_vad_sensitivity_result(None)

        self.assertEqual(
            called, [True],
            "_restart_vad_if_active must be called even when user cancels (result=None)",
        )



if __name__ == "__main__":
    unittest.main()
