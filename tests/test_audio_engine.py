"""
Unit tests for client/audio_engine.py — VAD and spectrum callback.

Covers:
  - AUDIO_AVAILABLE / WEBRTC_AVAILABLE flags
  - AudioEngine._input_callback: VAD callback behaviour
  - AudioEngine._input_callback: spectrum callback
  - AudioEngine default values
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio

import client.audio_engine as ae
from client.audio_engine import _BLOCKSIZE


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_indata(amplitude: int = 1000) -> np.ndarray:
    """Return a (320, 1) int16 array filled with a 1 kHz sine, as sounddevice would."""
    t = np.linspace(0, _BLOCKSIZE / 16000, _BLOCKSIZE, endpoint=False)
    pcm = (amplitude * np.sin(2 * np.pi * 1000 * t)).astype(np.int16)
    return pcm.reshape(-1, 1)


def _make_noise(amplitude: int = 200) -> np.ndarray:
    """Return low-amplitude white-noise indata simulating background noise."""
    rng = np.random.default_rng(seed=42)
    pcm = rng.integers(-amplitude, amplitude, size=_BLOCKSIZE, dtype=np.int16)
    return pcm.reshape(-1, 1)


def _make_engine() -> ae.AudioEngine:
    """Build an AudioEngine bypassing real audio streams."""
    engine = ae.AudioEngine.__new__(ae.AudioEngine)
    engine._loop = MagicMock()
    engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
    engine._stream = None
    engine._vad_active = False
    engine._vad_callback = None
    engine._vad_voice_state = False
    engine._energy_callback = None
    engine._spectrum_callback = None
    engine._vad_threshold = 250.0
    return engine


# ── Flag tests ────────────────────────────────────────────────────────────────

class TestFlags(unittest.TestCase):

    def test_audio_available_is_bool(self):
        self.assertIsInstance(ae.AUDIO_AVAILABLE, bool)

    def test_webrtc_available_is_bool(self):
        self.assertIsInstance(ae.WEBRTC_AVAILABLE, bool)

    def test_webrtc_available_implies_audio_available(self):
        if ae.WEBRTC_AVAILABLE:
            self.assertTrue(ae.AUDIO_AVAILABLE)


# ── AudioEngine._input_callback ───────────────────────────────────────────────

class TestInputCallbackSpectrum(unittest.TestCase):
    """Spectrum callback receives raw indata bytes on every frame."""

    def test_spectrum_callback_receives_raw_bytes(self):
        engine = _make_engine()
        received = []
        engine._spectrum_callback = lambda b: received.append(b)

        indata = _make_indata()
        engine._input_callback(indata, _BLOCKSIZE, {}, None)

        self.assertTrue(received)
        self.assertEqual(received[0], indata.tobytes())

    def test_spectrum_callback_not_called_when_none(self):
        engine = _make_engine()
        engine._spectrum_callback = None
        try:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        except Exception as exc:
            self.fail(f"callback raised unexpectedly: {exc}")


# ── AudioEngine default values ────────────────────────────────────────────────

class TestAudioEngineDefaults(unittest.TestCase):

    def test_vad_active_default_false(self):
        engine = ae.AudioEngine()
        self.assertFalse(engine._vad_active)


# ── AudioEngine VAD callback ──────────────────────────────────────────────────

class TestVadCallback(unittest.TestCase):

    def _make_vad_engine(self, threshold: float = 100.0):
        engine = _make_engine()
        engine._vad_active = True
        engine._vad_threshold = threshold
        return engine

    def test_vad_callback_fired_on_voice_onset(self):
        """High-amplitude frame exceeding threshold should fire callback with True."""
        called_with = []
        engine = self._make_vad_engine(threshold=100.0)
        engine._vad_callback = lambda v: called_with.append(v)
        engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)

        loud = _make_indata(amplitude=5000)  # RMS >> 100
        engine._input_callback(loud, _BLOCKSIZE, {}, None)

        self.assertIn(True, called_with)

    def test_vad_callback_fired_on_silence_after_voice(self):
        """Transition from voice to silence should fire callback with False."""
        called_with = []
        engine = self._make_vad_engine(threshold=100.0)
        engine._vad_voice_state = True  # simulate was-in-voice state
        engine._vad_callback = lambda v: called_with.append(v)
        engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)

        quiet = _make_noise(amplitude=1)  # RMS << 100
        engine._input_callback(quiet, _BLOCKSIZE, {}, None)

        self.assertIn(False, called_with)

    def test_vad_no_duplicate_callbacks_when_state_unchanged(self):
        """Callback should not fire again if voice state has not changed."""
        called_with = []
        engine = self._make_vad_engine(threshold=100.0)
        engine._vad_voice_state = True  # already in voice
        engine._vad_callback = lambda v: called_with.append(v)
        engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)

        loud = _make_indata(amplitude=5000)
        engine._input_callback(loud, _BLOCKSIZE, {}, None)
        engine._input_callback(loud, _BLOCKSIZE, {}, None)

        # Should fire at most once (the state doesn't change on 2nd call)
        self.assertLessEqual(called_with.count(True), 1)


class TestAudioEngineDevice(unittest.TestCase):

    @patch("sounddevice.InputStream")
    def test_start_passes_device_to_input_stream(self, mock_cls):
        """AudioEngine.start(loop, device='Mic') passes device= to sd.InputStream."""
        from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice not available")
        mock_cls.return_value = MagicMock()
        engine = AudioEngine()
        loop = MagicMock()
        engine.start(loop, device="Mic")
        engine.stop()
        call_kwargs = mock_cls.call_args_list[0][1]
        self.assertEqual(call_kwargs.get("device"), "Mic")

    @patch("sounddevice.InputStream")
    def test_start_no_device_when_none(self, mock_cls):
        """AudioEngine.start(loop, device=None) does not pass device= to sd.InputStream."""
        from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice not available")
        mock_cls.return_value = MagicMock()
        engine = AudioEngine()
        loop = MagicMock()
        engine.start(loop, device=None)
        engine.stop()
        call_kwargs = mock_cls.call_args_list[0][1]
        self.assertNotIn("device", call_kwargs)

    @patch("sounddevice.InputStream")
    def test_start_vad_passes_device(self, mock_cls):
        """AudioEngine.start_vad(loop, ..., device='Mic') forwards device= to start()."""
        from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice not available")
        mock_cls.return_value = MagicMock()
        engine = AudioEngine()
        loop = MagicMock()
        engine.start_vad(loop, threshold=100.0, callback=lambda v: None, device="Headset")
        engine.stop()
        call_kwargs = mock_cls.call_args_list[0][1]
        self.assertEqual(call_kwargs.get("device"), "Headset")

    @patch("sounddevice.InputStream")
    def test_start_falls_back_on_bad_device(self, mock_cls):
        """AudioEngine.start() falls back to system default if device raises."""
        from client.audio_engine import AudioEngine, AUDIO_AVAILABLE
        if not AUDIO_AVAILABLE:
            self.skipTest("sounddevice not available")
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("device") == "Bad Device":
                raise ValueError("device not found")
            return MagicMock()

        mock_cls.side_effect = side_effect
        engine = AudioEngine()
        loop = MagicMock()
        engine.start(loop, device="Bad Device")
        engine.stop()
        # First call: device="Bad Device" (raises), second: fallback (no device)
        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
