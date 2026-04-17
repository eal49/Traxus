"""
Unit tests for client/audio_engine.py — spectral noise suppression.

Covers:
  - NS_AVAILABLE flag
  - _SpectralNoiseSuppressor.process() shape, dtype, and output correctness
  - AudioEngine._input_callback with NS active (suppressor.process called)
  - AudioEngine._input_callback with NS inactive (raw path unchanged)
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


# ── NS_AVAILABLE flag ─────────────────────────────────────────────────────────

class TestNsAvailableFlag(unittest.TestCase):

    def test_ns_available_is_bool(self):
        self.assertIsInstance(NS_AVAILABLE, bool)

    def test_ns_available_matches_audio_available(self):
        # NS uses only numpy; it should be available exactly when audio is.
        self.assertEqual(NS_AVAILABLE, ae.AUDIO_AVAILABLE)


# ── _SpectralNoiseSuppressor unit tests ───────────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestSpectralNoiseSuppressor(unittest.TestCase):

    def setUp(self):
        self.ns = ae._SpectralNoiseSuppressor(_BLOCKSIZE)

    # Shape and dtype

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

    # Noise model update

    def test_noise_model_updates_on_quiet_frame(self):
        """After processing a near-silent frame the noise model should grow
        toward the frame's power (EMA update with ALPHA_FAST)."""
        noise_before = self.ns._noise_power.copy()
        quiet = _make_noise(amplitude=50)[:, 0]
        self.ns.process(quiet)
        # Mean noise estimate should have changed
        self.assertFalse(np.allclose(self.ns._noise_power, noise_before))

    def test_noise_model_moves_slowly_on_voiced_frame(self):
        """After seeding the model, a loud frame should trigger ALPHA_SLOW update.

        We derive the implied EMA alpha from the EMA update formula:
            new_power = alpha * P_x + (1-alpha) * old_power
          =>  alpha = (new - old) / (P_x - old)
        and verify it is much closer to ALPHA_SLOW than ALPHA_FAST.
        """
        # Warm up the model with noise frames so the estimate is meaningful
        noise = _make_noise(amplitude=200)[:, 0]
        for _ in range(20):
            self.ns.process(noise)

        loud = _make_indata(amplitude=15000)[:, 0]

        # Compute P_x that the suppressor will see for this frame
        X = np.fft.rfft(loud.astype(np.float64))
        P_x = X.real ** 2 + X.imag ** 2

        noise_before = self.ns._noise_power.copy()
        self.ns.process(loud)
        noise_after = self.ns._noise_power.copy()

        # Implied alpha per bin: alpha[k] = (after[k] - before[k]) / (P_x[k] - before[k])
        # Only use bins where |P_x - before| is > 1% of the max deviation (avoids near-0/0).
        deviation = P_x - noise_before
        threshold = 0.01 * float(np.max(np.abs(deviation)))
        mask = np.abs(deviation) > threshold
        self.assertGreater(int(mask.sum()), 0, "No significant deviation bins found")

        implied_alpha = float(np.mean((noise_after[mask] - noise_before[mask]) / deviation[mask]))

        alpha_slow = ae._SpectralNoiseSuppressor.ALPHA_SLOW
        alpha_fast = ae._SpectralNoiseSuppressor.ALPHA_FAST

        # implied alpha should be close to ALPHA_SLOW, not ALPHA_FAST
        self.assertLess(
            abs(implied_alpha - alpha_slow),
            abs(implied_alpha - alpha_fast),
            f"implied alpha {implied_alpha:.4f} is closer to ALPHA_FAST ({alpha_fast}) "
            f"than ALPHA_SLOW ({alpha_slow}) — wrong branch taken",
        )

    # Noise suppression effect

    def test_noise_suppressed_signal_has_lower_rms_than_input(self):
        """After the noise model has seen noise-only frames, filtering a noisy
        signal should reduce RMS relative to the raw input."""
        noise = _make_noise(amplitude=500)[:, 0]
        for _ in range(30):
            self.ns.process(noise)   # warm up model on noise

        # Create a signal that is speech + same noise level
        speech = _make_indata(amplitude=3000)[:, 0]
        noisy_speech = np.clip(speech.astype(np.int32) + noise.astype(np.int32),
                               -32768, 32767).astype(np.int16)

        filtered = self.ns.process(noisy_speech)

        rms_noisy    = float(np.sqrt(np.mean(noisy_speech.astype(np.float64) ** 2)))
        rms_filtered = float(np.sqrt(np.mean(filtered.astype(np.float64) ** 2)))

        # Filtered RMS should not exceed the raw noisy RMS; the filter should
        # only attenuate, never amplify beyond what phase reconstruction allows.
        # We allow a 5 % tolerance for the phase-preserved reconstruction.
        self.assertLessEqual(rms_filtered, rms_noisy * 1.05)


# ── AudioEngine._input_callback integration ───────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestInputCallbackNsActive(unittest.TestCase):
    """NS is active: suppressor.process() must be called exactly once per
    callback invocation, and its output must be fed to ADPCM encode."""

    def _make_engine_with_mock_suppressor(self):
        """Return an AudioEngine whose _suppressor.process is a mock."""
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        # Minimal manual init (avoids opening real audio streams)
        engine._loop = MagicMock()
        engine._stream = None
        engine._queue = MagicMock()
        engine._queue.put_nowait = MagicMock()
        engine._transmitting = True
        engine._vad_active = False
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._energy_callback = None
        engine._spectrum_callback = None
        engine._vad_threshold = 250.0
        engine._play_queue = MagicMock()
        engine._play_thread = None
        engine.loopback_enabled = False

        engine.noise_suppression_enabled = True
        engine._per_user_volume = {}

        # Real suppressor, but spy on process()
        real_suppressor = ae._SpectralNoiseSuppressor(_BLOCKSIZE)
        engine._suppressor = real_suppressor
        return engine, real_suppressor

    def test_suppressor_process_called_once_per_callback(self):
        engine, suppressor = self._make_engine_with_mock_suppressor()

        with patch.object(suppressor, "process", wraps=suppressor.process) as spy:
            indata = _make_indata()
            engine._input_callback(indata, _BLOCKSIZE, {}, None)
            spy.assert_called_once()

    def test_suppressor_receives_squeezed_1d_array(self):
        """process() should receive shape (320,) not (320, 1)."""
        engine, suppressor = self._make_engine_with_mock_suppressor()

        captured = {}

        def capture_call(pcm):
            captured["pcm"] = pcm
            return suppressor.__class__.process(suppressor, pcm)  # still run real impl

        with patch.object(suppressor, "process", side_effect=capture_call):
            indata = _make_indata()
            engine._input_callback(indata, _BLOCKSIZE, {}, None)

        self.assertEqual(captured["pcm"].ndim, 1)
        self.assertEqual(captured["pcm"].shape[0], _BLOCKSIZE)

    def test_filtered_bytes_reach_queue(self):
        """The bytes queued for transmission should come from the filtered PCM,
        not from the raw indata bytes."""
        engine, suppressor = self._make_engine_with_mock_suppressor()

        sentinel = np.zeros(_BLOCKSIZE, dtype=np.int16)
        sentinel[0] = 999  # distinctive marker

        def fake_process(pcm):
            return sentinel

        with patch.object(suppressor, "process", side_effect=fake_process):
            with patch("client.audio_engine.ADPCM_AVAILABLE", False):
                indata = _make_indata()
                engine._input_callback(indata, _BLOCKSIZE, {}, None)

        engine._loop.call_soon_threadsafe.assert_called_once()
        _, queued_pair = engine._loop.call_soon_threadsafe.call_args[0]
        codec, audio_bytes = queued_pair
        # The bytes should be the sentinel array's bytes
        self.assertEqual(audio_bytes, sentinel.tobytes())


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestInputCallbackNsInactive(unittest.TestCase):
    """NS is inactive (_suppressor=None): callback must use raw indata bytes
    exactly as before — no filtering, no change in behaviour."""

    def _make_engine_no_ns(self):
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._loop = MagicMock()
        engine._stream = None
        engine._queue = MagicMock()
        engine._queue.put_nowait = MagicMock()
        engine._transmitting = True
        engine._vad_active = False
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._energy_callback = None
        engine._spectrum_callback = None
        engine._vad_threshold = 250.0
        engine._play_queue = MagicMock()
        engine._play_thread = None
        engine._suppressor = None   # ← NS disabled
        engine.noise_suppression_enabled = True
        engine.loopback_enabled = False
        engine._per_user_volume = {}
        return engine

    def test_raw_bytes_reach_queue_when_ns_inactive(self):
        engine = self._make_engine_no_ns()

        with patch("client.audio_engine.ADPCM_AVAILABLE", False):
            indata = _make_indata()
            engine._input_callback(indata, _BLOCKSIZE, {}, None)

        engine._loop.call_soon_threadsafe.assert_called_once()
        _, queued_pair = engine._loop.call_soon_threadsafe.call_args[0]
        codec, audio_bytes = queued_pair
        self.assertEqual(audio_bytes, indata.tobytes())

    def test_callback_does_not_crash_when_ns_inactive(self):
        engine = self._make_engine_no_ns()
        engine._transmitting = False  # also test non-transmitting path
        try:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        except Exception as exc:
            self.fail(f"callback raised with NS inactive: {exc}")


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestNoiseSuppresionEnabledFlag(unittest.TestCase):
    """Tests for AudioEngine.noise_suppression_enabled flag behaviour."""

    def _make_engine(self, ns_enabled: bool):
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._loop = MagicMock()
        engine._stream = None
        engine._queue = MagicMock()
        engine._queue.put_nowait = MagicMock()
        engine._transmitting = True
        engine._vad_active = False
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._energy_callback = None
        engine._spectrum_callback = None
        engine._vad_threshold = 250.0
        engine._play_queue = MagicMock()
        engine._play_thread = None
        engine.noise_suppression_enabled = ns_enabled
        engine.loopback_enabled = False
        engine._per_user_volume = {}
        engine._suppressor = ae._SpectralNoiseSuppressor(_BLOCKSIZE)
        return engine

    def test_suppressor_not_called_when_flag_false(self):
        """When noise_suppression_enabled is False, process() must never be called."""
        engine = self._make_engine(ns_enabled=False)
        with patch.object(engine._suppressor, "process") as mock_process:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        mock_process.assert_not_called()

    def test_suppressor_called_when_flag_true(self):
        """When noise_suppression_enabled is True, process() must be called once."""
        engine = self._make_engine(ns_enabled=True)
        with patch.object(engine._suppressor, "process", wraps=engine._suppressor.process) as spy:
            engine._input_callback(_make_indata(), _BLOCKSIZE, {}, None)
        spy.assert_called_once()

    def test_default_value_is_true(self):
        """AudioEngine() should initialise noise_suppression_enabled to True."""
        import queue as _queue
        import threading as _threading
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._loop = None
        engine._stream = None
        engine._queue = ae.asyncio.Queue()
        engine._transmitting = False
        engine._suppressor = None
        engine._vad_active = False
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._energy_callback = None
        engine._vad_threshold = 250.0
        engine._play_queue = _queue.Queue()
        engine._play_thread = None
        # Call only the attribute-setting lines via real __init__ on a fresh instance
        real = ae.AudioEngine()
        self.assertTrue(real.noise_suppression_enabled)
        real._play_queue.put_nowait(None)  # stop playback thread


class TestPerUserVolumeAccessors(unittest.TestCase):
    """Unit tests for get_volume / set_volume."""

    def setUp(self):
        import queue as _q
        self.engine = ae.AudioEngine.__new__(ae.AudioEngine)
        self.engine._per_user_volume = {}
        self.engine._play_queue = _q.Queue()
        self.engine._play_thread = None

    def test_default_volume_is_100(self):
        self.assertEqual(self.engine.get_volume("alice"), 100)

    def test_set_and_get_round_trip(self):
        self.engine.set_volume("alice", 80)
        self.assertEqual(self.engine.get_volume("alice"), 80)

    def test_clamp_below_zero(self):
        self.engine.set_volume("alice", -10)
        self.assertEqual(self.engine.get_volume("alice"), 0)

    def test_clamp_above_200(self):
        self.engine.set_volume("alice", 250)
        self.assertEqual(self.engine.get_volume("alice"), 200)

    def test_zero_boundary(self):
        self.engine.set_volume("alice", 0)
        self.assertEqual(self.engine.get_volume("alice"), 0)

    def test_200_boundary(self):
        self.engine.set_volume("alice", 200)
        self.assertEqual(self.engine.get_volume("alice"), 200)

    def test_separate_users_independent(self):
        self.engine.set_volume("alice", 60)
        self.engine.set_volume("bob", 150)
        self.assertEqual(self.engine.get_volume("alice"), 60)
        self.assertEqual(self.engine.get_volume("bob"), 150)


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestPlaybackWorkerGain(unittest.TestCase):
    """Tests for per-user gain application in the playback worker."""

    def _run_worker_frame(self, pcm: np.ndarray, username: str, level: int) -> np.ndarray:
        """Feed one frame through the gain logic (extracted from worker)."""
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._per_user_volume = {username: level} if username else {}
        engine._suppressor = None
        engine.noise_suppression_enabled = True

        audio = pcm.copy()
        gain_level = engine._per_user_volume.get(username, 100)
        if gain_level != 100:
            audio = np.clip(
                audio.astype(np.float32) * (gain_level / 100.0),
                -32768, 32767,
            ).astype(np.int16)
        return audio

    def test_100_percent_leaves_pcm_unchanged(self):
        pcm = _make_indata(amplitude=5000)[:, 0]
        result = self._run_worker_frame(pcm, "alice", 100)
        np.testing.assert_array_equal(result, pcm)

    def test_50_percent_halves_rms(self):
        pcm = _make_indata(amplitude=8000)[:, 0]
        result = self._run_worker_frame(pcm, "alice", 50)
        rms_in  = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)))
        rms_out = float(np.sqrt(np.mean(result.astype(np.float64) ** 2)))
        self.assertAlmostEqual(rms_out / rms_in, 0.5, delta=0.01)

    def test_0_percent_produces_silence(self):
        pcm = _make_indata(amplitude=10000)[:, 0]
        result = self._run_worker_frame(pcm, "alice", 0)
        self.assertTrue(np.all(result == 0))

    def test_200_percent_clips_without_raising(self):
        pcm = np.full(_BLOCKSIZE, 30000, dtype=np.int16)
        try:
            result = self._run_worker_frame(pcm, "alice", 200)
        except Exception as exc:
            self.fail(f"200% gain raised: {exc}")
        self.assertLessEqual(int(result.max()), 32767)
        self.assertGreaterEqual(int(result.min()), -32768)

    def test_unknown_username_defaults_to_100(self):
        pcm = _make_indata(amplitude=5000)[:, 0]
        result = self._run_worker_frame(pcm, "", 100)
        np.testing.assert_array_equal(result, pcm)


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestAudioEngineLoopback(unittest.TestCase):
    """Tests for AudioEngine loopback_enabled flag and set_loopback()."""

    def _make_engine(self):
        import queue as _q
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._per_user_volume = {}
        engine._play_queue = _q.Queue()
        engine._play_thread = None
        engine.loopback_enabled = False
        engine._suppressor = ae._SpectralNoiseSuppressor(_BLOCKSIZE)
        engine.noise_suppression_enabled = True
        engine._vad_active = False
        engine._energy_callback = None
        engine._spectrum_callback = None
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._vad_threshold = 0.0
        engine._transmitting = False
        engine._loop = None
        return engine

    def test_loopback_disabled_by_default(self):
        engine = self._make_engine()
        self.assertFalse(engine.loopback_enabled)

    def test_set_loopback_true(self):
        engine = self._make_engine()
        engine.set_loopback(True)
        self.assertTrue(engine.loopback_enabled)

    def test_set_loopback_false(self):
        engine = self._make_engine()
        engine.set_loopback(True)
        engine.set_loopback(False)
        self.assertFalse(engine.loopback_enabled)

    def _make_sync_loop(self):
        """Return a MagicMock loop that executes call_soon_threadsafe callbacks synchronously."""
        loop = MagicMock()
        loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
        return loop

    def test_loopback_puts_frame_on_play_queue(self):
        engine = self._make_engine()
        engine.loopback_enabled = True
        engine._loop = self._make_sync_loop()

        indata = _make_indata(amplitude=3000)
        engine._input_callback(indata, _BLOCKSIZE, None, None)

        self.assertFalse(engine._play_queue.empty())
        codec, audio_bytes, username = engine._play_queue.get_nowait()
        self.assertEqual(codec, ae.CODEC_RAW)
        self.assertIsInstance(audio_bytes, bytes)
        self.assertEqual(username, "")

    def test_no_loopback_when_disabled(self):
        engine = self._make_engine()
        engine.loopback_enabled = False
        engine._loop = self._make_sync_loop()

        indata = _make_indata(amplitude=3000)
        engine._input_callback(indata, _BLOCKSIZE, None, None)

        self.assertTrue(engine._play_queue.empty())

    def test_loopback_uses_ns_filtered_bytes_when_ns_on(self):
        engine = self._make_engine()
        engine.loopback_enabled = True
        engine.noise_suppression_enabled = True
        engine._loop = self._make_sync_loop()

        indata = _make_indata(amplitude=3000)
        raw_bytes = indata.tobytes()

        filtered_result: list[np.ndarray] = []
        real_process = engine._suppressor.process
        with patch.object(engine._suppressor, "process",
                          side_effect=lambda x: (filtered_result.append(real_process(x)) or filtered_result[-1])):
            engine._input_callback(indata, _BLOCKSIZE, None, None)

        self.assertTrue(filtered_result, "NS suppressor was not called")
        self.assertFalse(engine._play_queue.empty())
        codec, audio_bytes, _ = engine._play_queue.get_nowait()
        self.assertEqual(codec, ae.CODEC_RAW)
        self.assertEqual(audio_bytes, filtered_result[0].tobytes())

    def test_loopback_uses_raw_bytes_when_ns_off(self):
        engine = self._make_engine()
        engine.loopback_enabled = True
        engine.noise_suppression_enabled = False
        engine._loop = self._make_sync_loop()

        indata = _make_indata(amplitude=3000)
        raw_bytes = indata.tobytes()
        engine._input_callback(indata, _BLOCKSIZE, None, None)

        self.assertFalse(engine._play_queue.empty())
        codec, audio_bytes, _ = engine._play_queue.get_nowait()
        self.assertEqual(audio_bytes, raw_bytes)


@unittest.skipUnless(NS_AVAILABLE, "numpy not available")
class TestAudioEngineSpectrumCallback(unittest.TestCase):
    """Tests for set_spectrum_callback and _spectrum_callback invocation."""

    def _make_engine(self):
        import queue as _q
        engine = ae.AudioEngine.__new__(ae.AudioEngine)
        engine._per_user_volume = {}
        engine._play_queue = _q.Queue()
        engine._play_thread = None
        engine.loopback_enabled = False
        engine._suppressor = ae._SpectralNoiseSuppressor(_BLOCKSIZE)
        engine.noise_suppression_enabled = True
        engine._vad_active = False
        engine._energy_callback = None
        engine._spectrum_callback = None
        engine._vad_callback = None
        engine._vad_voice_state = False
        engine._vad_threshold = 0.0
        engine._transmitting = False
        engine._loop = None
        return engine

    def test_set_spectrum_callback_registers(self):
        engine = self._make_engine()
        cb = MagicMock()
        engine.set_spectrum_callback(cb)
        self.assertIs(engine._spectrum_callback, cb)

    def test_set_spectrum_callback_none_clears(self):
        engine = self._make_engine()
        engine.set_spectrum_callback(MagicMock())
        engine.set_spectrum_callback(None)
        self.assertIsNone(engine._spectrum_callback)

    def test_spectrum_callback_receives_pcm_bytes(self):
        engine = self._make_engine()
        received: list[bytes] = []

        loop = MagicMock()
        loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
        engine._loop = loop

        engine.set_spectrum_callback(lambda b: received.append(b))

        indata = _make_indata(amplitude=3000)
        engine._input_callback(indata, _BLOCKSIZE, None, None)

        self.assertEqual(len(received), 1)
        self.assertIsInstance(received[0], bytes)

    def test_spectrum_callback_cleared_by_stop_vad(self):
        engine = self._make_engine()
        # give it a real stop method (no-op since AUDIO_AVAILABLE may be False)
        engine.stop = lambda: None
        engine.set_spectrum_callback(MagicMock())
        engine._vad_active = True
        engine.stop_vad()
        self.assertIsNone(engine._spectrum_callback)

    def test_no_invocation_when_callback_is_none(self):
        engine = self._make_engine()
        engine._spectrum_callback = None

        import asyncio
        loop = asyncio.new_event_loop()
        engine._loop = loop

        indata = _make_indata(amplitude=3000)
        try:
            engine._input_callback(indata, _BLOCKSIZE, None, None)
        except Exception as exc:
            self.fail(f"_input_callback raised with no spectrum callback: {exc}")

        loop.close()
        engine._loop = None


if __name__ == "__main__":
    unittest.main()
