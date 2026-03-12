"""
Tests for the VAD custom-sensitivity / calibration feature.

Covers:
  - _get_vad_threshold() returns named-level values
  - _get_vad_threshold() returns _vad_custom_threshold for "custom"
  - AudioEngine.set_energy_callback sets and clears the callback
  - stop_vad() clears _energy_callback
  - vad_custom_threshold default is 50.0 in load_settings() for a missing file
  - vad_custom_threshold round-trips through save_settings() / load_settings()
"""
import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
from client.app import TraxusApp, _VAD_SENSITIVITY_THRESHOLDS


class TestGetVadThreshold(unittest.TestCase):
    """_get_vad_threshold() resolves named levels and the custom level."""

    def _make_app(self, sensitivity: str, custom: float = 50.0) -> TraxusApp:
        """Return a minimal TraxusApp-like object with the required attributes."""
        app = TraxusApp.__new__(TraxusApp)
        app._vad_sensitivity = sensitivity
        app._vad_custom_threshold = custom
        return app

    def test_named_level_low(self):
        app = self._make_app("low")
        self.assertEqual(app._get_vad_threshold(), _VAD_SENSITIVITY_THRESHOLDS["low"])

    def test_named_level_medium(self):
        app = self._make_app("medium")
        self.assertEqual(app._get_vad_threshold(), _VAD_SENSITIVITY_THRESHOLDS["medium"])

    def test_named_level_high(self):
        app = self._make_app("high")
        self.assertEqual(app._get_vad_threshold(), _VAD_SENSITIVITY_THRESHOLDS["high"])

    def test_named_level_very_high(self):
        app = self._make_app("very_high")
        self.assertEqual(app._get_vad_threshold(), _VAD_SENSITIVITY_THRESHOLDS["very_high"])

    def test_custom_returns_custom_threshold(self):
        app = self._make_app("custom", custom=123.0)
        self.assertEqual(app._get_vad_threshold(), 123.0)

    def test_custom_uses_app_attribute_not_table(self):
        app = self._make_app("custom", custom=77.5)
        # Must not be a named-level value
        self.assertNotIn(app._get_vad_threshold(), _VAD_SENSITIVITY_THRESHOLDS.values())
        self.assertEqual(app._get_vad_threshold(), 77.5)


class TestAudioEngineEnergyCallback(unittest.TestCase):
    """set_energy_callback stores and clears the callback; stop_vad clears it."""

    def setUp(self):
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice/numpy not available")
        self.engine = AudioEngine()

    def test_set_energy_callback_stores_callback(self):
        cb = MagicMock()
        self.engine.set_energy_callback(cb)
        self.assertIs(self.engine._energy_callback, cb)

    def test_set_energy_callback_clears_with_none(self):
        self.engine.set_energy_callback(MagicMock())
        self.engine.set_energy_callback(None)
        self.assertIsNone(self.engine._energy_callback)

    def test_stop_vad_clears_energy_callback(self):
        self.engine._energy_callback = MagicMock()
        self.engine._vad_active = True
        self.engine._stream = None  # prevent actual stream stop
        # Patch stop() to avoid real device access
        self.engine.stop = MagicMock()
        self.engine.stop_vad()
        self.assertIsNone(self.engine._energy_callback)


class TestVadCustomThresholdSettings(unittest.TestCase):
    """vad_custom_threshold default and round-trip through settings."""

    def test_default_is_50(self):
        from client import settings as s_mod
        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "nonexistent.json"
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original
        self.assertEqual(loaded.get("vad_custom_threshold", 50.0), 50.0)

    def test_round_trip(self):
        from client import settings as s_mod
        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "settings.json"
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                s_mod.save_settings({
                    "ptt_key": "f9",
                    "ptt_mode": "vad",
                    "vad_sensitivity": "custom",
                    "vad_custom_threshold": 87.0,
                })
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original
        self.assertEqual(loaded["vad_custom_threshold"], 87.0)

    def test_missing_key_uses_default(self):
        from client import settings as s_mod
        with tempfile.TemporaryDirectory() as tmp:
            fake_file = Path(tmp) / "settings.json"
            fake_file.write_text(
                json.dumps({"ptt_key": "f9", "ptt_mode": "toggle", "vad_sensitivity": "high"}),
                encoding="utf-8",
            )
            original = s_mod._SETTINGS_FILE
            s_mod._SETTINGS_FILE = fake_file
            try:
                loaded = s_mod.load_settings()
            finally:
                s_mod._SETTINGS_FILE = original
        self.assertEqual(loaded.get("vad_custom_threshold", 50.0), 50.0)


if __name__ == "__main__":
    unittest.main()
