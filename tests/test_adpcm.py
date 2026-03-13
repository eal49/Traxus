"""Tests for shared/adpcm.py — IMA ADPCM encode/decode."""
import struct
import unittest

import numpy as np

from shared.adpcm import CODEC_ADPCM, CODEC_RAW, decode, encode


class TestAdpcmConstants(unittest.TestCase):
    def test_codec_values(self):
        self.assertEqual(CODEC_RAW, 0)
        self.assertEqual(CODEC_ADPCM, 1)


class TestAdpcmEncode(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(encode(b""), b"")

    def test_output_length_approx_4x_compression(self):
        # 640 bytes of PCM (320 samples) → 4-byte header + 160 nibble bytes = 164 bytes
        pcm = np.zeros(320, dtype="<i2").tobytes()
        out = encode(pcm)
        self.assertLessEqual(len(out), 164)

    def test_output_has_header(self):
        pcm = np.ones(320, dtype="<i2").tobytes()
        out = encode(pcm)
        # Must be at least 4 bytes (header)
        self.assertGreaterEqual(len(out), 4)

    def test_encode_voice_like_signal(self):
        # 320 samples of 400 Hz sine at 16 kHz (realistic voice frame)
        t = np.arange(320) / 16000.0
        signal = (np.sin(2 * np.pi * 400 * t) * 8000).astype(np.int16)
        pcm = signal.tobytes()
        out = encode(pcm)
        # ~4× compression: 640 bytes PCM → ≤ 164 bytes ADPCM
        self.assertLessEqual(len(out), 164)


class TestAdpcmDecode(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        self.assertEqual(decode(b""), b"")

    def test_decode_invalid_short_raises(self):
        with self.assertRaises(ValueError):
            decode(b"\x00\x00")  # header requires 4 bytes


class TestAdpcmRoundTrip(unittest.TestCase):
    def _rms(self, samples: np.ndarray) -> float:
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))

    def test_roundtrip_length_preserved(self):
        t = np.arange(320) / 16000.0
        original = (np.sin(2 * np.pi * 400 * t) * 8000).astype(np.int16)
        pcm_in = original.tobytes()
        pcm_out = decode(encode(pcm_in))
        reconstructed = np.frombuffer(pcm_out, dtype="<i2")
        self.assertEqual(len(reconstructed), len(original))

    def test_roundtrip_rms_error_under_5_percent(self):
        # Use 4000 samples (250ms) so the ADPCM cold-start warmup (~10 samples)
        # is a small fraction and overall RMS error stays below the 5% threshold.
        t = np.arange(4000) / 16000.0
        original = (np.sin(2 * np.pi * 400 * t) * 8000).astype(np.int16)
        pcm_in = original.tobytes()
        pcm_out = decode(encode(pcm_in))
        reconstructed = np.frombuffer(pcm_out, dtype="<i2")
        self.assertEqual(len(reconstructed), len(original))
        diff = original.astype(np.float64) - reconstructed.astype(np.float64)
        rms_diff = float(np.sqrt(np.mean(diff ** 2)))
        rms_orig = self._rms(original)
        if rms_orig > 0:
            self.assertLess(rms_diff / rms_orig, 0.05)

    def test_roundtrip_silence(self):
        pcm = np.zeros(320, dtype="<i2").tobytes()
        out = decode(encode(pcm))
        reconstructed = np.frombuffer(out, dtype="<i2")
        self.assertEqual(len(reconstructed), 320)
        # All samples should be zero or very close (silence stays silent)
        self.assertTrue(np.all(np.abs(reconstructed) <= 16))


if __name__ == "__main__":
    unittest.main()
