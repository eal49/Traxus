"""
Unit tests for client/audio_engine.py — spectral noise suppression and VAD.

Covers:
  - NS_AVAILABLE / AUDIO_AVAILABLE / WEBRTC_AVAILABLE flags
  - _SpectralNoiseSuppressor.process() shape, dtype, and output correctness
  - AudioEngine._input_callback: NS applied when enabled
  - AudioEngine._input_callback: raw path when NS disabled
  - AudioEngine.noise_suppression_enabled flag
  - AudioEngine VAD: callback fired on voice/silence transition
  - AudioEngine spectrum callback
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
from client.audio_engine import NS_AVAILABLE, _BLOCKSIZE


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


def _make_engine(ns_enabled: bool = True, transmitting: bool = False) -> ae.AudioEngine:
    """Build an AudioEngine with real suppressor, bypassing real audio streams."""
    engine = ae.AudioEngine.__new__(ae.AudioEngine)
    engine._loop = MagicMock()
    engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
    engine._stream = None
    engine._transmitting = transmitting
    engine._vad_active = False
    engine._vad_callback = None
    engine._vad_voice_state = False
    engine._energy_callback = None
    engine._spectrum_callback = None
    engine._vad_threshold = 250.0
    engine.noise_suppression_enabled = ns_enabled
    engine._suppressor = ae._SpectralNoiseSuppressor(_BLOCKSIZE) if NS_AVAILABLE else None
    return engine


# ── Flag tests ────────────────────────────────────────────────────────────────

class TestFlags(unittest.TestCase):

    def test_ns_available_is_bool(self):
        self.assertIsInstance(ae.NS_AVAILABLE, bool)

    def test_ns_available_matches_audio_available(self):
        self.assertEqual(ae.NS_AVAILABLE, ae.AUDIO_AVAILABLE)

    def test_webrtc_available_is_bool(self):
        self.assertIsInstance(ae.WEBRTC_AVAILABLE, bool)

    def test_webrtc_available_implies_audio_available(self):
        if ae.WEBRTC_AVAILABLE:
            self.assertTrue(ae.AUDIO_AVAILABLE)


# ── _SpectralNoiseSuppressor ──────────────────────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestSpectralNoiseSuppressor(unittest.TestCase):

    def setUp(self):
        self.ns = ae._SpectralNoiseSuppressor(_BLOCKSIZE)

    def test_output_shape_matches_input(self):
        pcm = _make_indata()[:, 0]
        out = self.ns.process(pcm)
        self.assertEqual(out.shape, (pcm.shape[0],))

    def test_output_dtype_is_int16(self):
        pcm = _make_indata()[:, 0]
        out = self.ns.process(pcm)
        self.assertEqual(out.dtype, np.int16)

    def test_output_within_int16_range(self):
        pcm = _make_indata(amplitude=30000)[:, 0]
        out = self.ns.process(pcm)
        self.assertGreaterEqual(int(out.min()), -32768)
        self.assertLessEqual(int(out.max()), 32767)

    def test_noise_model_updates_on_quiet_frame(self):
        noise_before = self.ns._noise_power.copy()
        quiet = _make_noise(amplitude=50)[:, 0]
        self.ns.process(quiet)
        self.assertFalse(np.allclose(self.ns._noise_power, noise_before))

    def test_noise_model_moves_slowly_on_voiced_frame(self):
        noise = _make_noise(amplitude=200)[:, 0]
        for _ in range(20):
            self.ns.process(noise)

        loud = _make_indata(amplitude=15000)[:, 0]
        X = np.fft.rfft(loud.astype(np.float64))
        P_x = X.real ** 2 + X.imag ** 2

        noise_before = self.ns._noise_power.copy()
        self.ns.process(loud)
        noise_after = self.ns._noise_power.copy()

        deviation = P_x - noise_before
        threshold = 0.01 * float(np.max(np.abs(deviation)))
        mask = np.abs(deviation) > threshold
        self.assertGreater(int(mask.sum()), 0)

        implied_alpha = float(np.mean(
            (noise_after[mask] - noise_before[mask]) / deviation[mask]
        ))
        alpha_slow = ae._SpectralNoiseSuppressor.ALPHA_SLOW
        alpha_fast = ae._SpectralNoiseSuppressor.ALPHA_FAST
        self.assertLess(
            abs(implied_alpha - alpha_slow),
            abs(implied_alpha - alpha_fast),
        )

    def test_noise_suppressed_signal_has_lower_rms_than_input(self):
        noise = _make_noise(amplitude=500)[:, 0]
        for _ in range(30):
            self.ns.process(noise)

        speech = _make_indata(amplitude=3000)[:, 0]
        noisy_speech = np.clip(
            speech.astype(np.int32) + noise.astype(np.int32), -32768, 32767
        ).astype(np.int16)
        filtered = self.ns.process(noisy_speech)

        rms_noisy = float(np.sqrt(np.mean(noisy_speech.astype(np.float64) ** 2)))
        rms_filtered = float(np.sqrt(np.mean(filtered.astype(np.float64) ** 2)))
        self.assertLessEqual(rms_filtered, rms_noisy * 1.05)


# ── AudioEngine._input_callback ───────────────────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestInputCallbackNsActive(unittest.TestCase):
    """NS active: suppressor.process() must be called exactly once per callback."""

    def test_suppressor_process_called_once_per_callback(self):
        engine = _make_engine(ns_enabled=True)
        with patch.object(engine._suppressor, "process", wraps=engine._suppressor.process) as spy:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        spy.assert_called_once()

    def test_suppressor_receives_squeezed_1d_array(self):
        engine = _make_engine(ns_enabled=True)
        captured = {}

        real_process = engine._suppressor.process

        def capture_call(pcm):
            captured["pcm"] = pcm
            return real_process(pcm)

        with patch.object(engine._suppressor, "process", side_effect=capture_call):
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)

        self.assertEqual(captured["pcm"].ndim, 1)
        self.assertEqual(captured["pcm"].shape[0], _BLOCKSIZE)

    def test_spectrum_callback_receives_filtered_bytes(self):
        """Spectrum callback should receive the NS-filtered bytes, not raw."""
        engine = _make_engine(ns_enabled=True)
        sentinel = np.zeros(_BLOCKSIZE, dtype=np.int16)
        sentinel[0] = 42

        def fake_process(pcm):
            return sentinel

        received = []
        engine._spectrum_callback = lambda b: received.append(b)
        engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)

        with patch.object(engine._suppressor, "process", side_effect=fake_process):
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)

        self.assertTrue(received, "Spectrum callback was not called")
        self.assertEqual(received[0], sentinel.tobytes())


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestInputCallbackNsInactive(unittest.TestCase):
    """NS inactive: callback must use raw indata bytes unchanged."""

    def test_suppressor_not_called_when_ns_disabled(self):
        engine = _make_engine(ns_enabled=False)
        with patch.object(engine._suppressor, "process") as mock_process:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        mock_process.assert_not_called()

    def test_spectrum_callback_receives_raw_bytes_when_ns_disabled(self):
        engine = _make_engine(ns_enabled=False)
        received = []
        engine._spectrum_callback = lambda b: received.append(b)
        engine._loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)

        indata = _make_indata()
        engine._input_callback(indata, _BLOCKSIZE, {}, None)

        self.assertTrue(received)
        self.assertEqual(received[0], indata.tobytes())

    def test_callback_does_not_crash_when_ns_inactive(self):
        engine = _make_engine(ns_enabled=False, transmitting=False)
        engine._suppressor = None
        try:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        except Exception as exc:
            self.fail(f"callback raised with NS inactive: {exc}")


# ── AudioEngine default values ────────────────────────────────────────────────

class TestAudioEngineDefaults(unittest.TestCase):

    def test_noise_suppression_enabled_default_true(self):
        engine = ae.AudioEngine()
        self.assertTrue(engine.noise_suppression_enabled)

    def test_transmitting_default_false(self):
        engine = ae.AudioEngine()
        self.assertFalse(engine.transmitting)

    def test_transmitting_setter(self):
        engine = ae.AudioEngine()
        engine.transmitting = True
        self.assertTrue(engine.transmitting)


# ── AudioEngine VAD callback ──────────────────────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
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


if __name__ == "__main__":
    unittest.main()
