"""
Unit tests for client/mic_track.py (task 4.6).

Tests:
  - MicTrack.recv() returns silence frames when not transmitting
  - MicTrack.recv() returns real audio frames when transmitting
  - Frame shape (320 samples) and pts sequencing
  - NS applied in _input_callback when noise_suppression_enabled=True
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import numpy as np
    import av  # noqa: F401
    import aiortc  # noqa: F401
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicTrackSilence(unittest.IsolatedAsyncioTestCase):
    """recv() must return silence when not transmitting."""

    async def test_silence_when_not_transmitting(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream

            track = MicTrack(loop)
            track.set_transmitting(False)

            frame = await track.recv()

        # Should be silence: all samples zero
        arr = frame.to_ndarray()
        self.assertTrue(
            (arr == 0).all(),
            "recv() must return a silence frame when not transmitting",
        )

    async def test_silence_frame_has_correct_sample_count(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.set_transmitting(False)
            frame = await track.recv()

        arr = frame.to_ndarray()
        self.assertEqual(arr.size, 320, "Silence frame must have 320 samples")


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicTrackAudio(unittest.IsolatedAsyncioTestCase):
    """recv() returns real audio when transmitting and queue has data."""

    async def test_recv_returns_queued_pcm(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.set_transmitting(True)

        pcm = (np.ones(320, dtype=np.int16) * 1000).tobytes()
        await track._queue.put(pcm)

        frame = await track.recv()
        arr = frame.to_ndarray().flatten()
        self.assertEqual(arr[0], 1000, "recv() must return the queued PCM samples")

    async def test_pts_increments_monotonically(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.set_transmitting(True)

        pts_values = []
        for i in range(3):
            pcm = (np.ones(320, dtype=np.int16) * i).tobytes()
            await track._queue.put(pcm)
            frame = await track.recv()
            pts_values.append(frame.pts)

        self.assertEqual(len(pts_values), 3)
        self.assertLess(pts_values[0], pts_values[1])
        self.assertLess(pts_values[1], pts_values[2])


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicTrackNoiseSuppression(unittest.IsolatedAsyncioTestCase):
    """_input_callback applies NS when noise_suppression_enabled=True."""

    async def test_ns_applied_when_enabled(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.noise_suppression_enabled = True
            track.set_transmitting(True)

        ns = track._suppressor
        if ns is None:
            self.skipTest("NS suppressor not available")

        with patch.object(ns, "process", wraps=ns.process) as spy:
            indata = (np.ones((320, 1), dtype=np.int16) * 500)
            track._input_callback(indata, 320, {}, None)

        spy.assert_called_once()

    async def test_ns_not_applied_when_disabled(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.noise_suppression_enabled = False
            track.set_transmitting(True)

        ns = track._suppressor
        if ns is None:
            self.skipTest("NS suppressor not available")

        with patch.object(ns, "process") as mock_process:
            indata = (np.ones((320, 1), dtype=np.int16) * 500)
            track._input_callback(indata, 320, {}, None)

        mock_process.assert_not_called()


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicTrackTransmitGate(unittest.IsolatedAsyncioTestCase):
    """_input_callback must only enqueue when transmitting."""

    async def test_callback_does_not_enqueue_when_not_transmitting(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.set_transmitting(False)

        indata = np.zeros((320, 1), dtype=np.int16)
        track._input_callback(indata, 320, {}, None)
        await asyncio.sleep(0)

        self.assertTrue(track._queue.empty(), "Queue must stay empty when not transmitting")

    async def test_callback_enqueues_when_transmitting(self):
        from client.mic_track import MicTrack

        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream_cls.return_value = MagicMock()
            track = MicTrack(loop)
            track.set_transmitting(True)

        indata = np.ones((320, 1), dtype=np.int16) * 200
        track._input_callback(indata, 320, {}, None)
        # call_soon_threadsafe schedules put_nowait; yield to the event loop
        await asyncio.sleep(0)

        self.assertFalse(track._queue.empty(), "Queue must receive a frame when transmitting")


if __name__ == "__main__":
    unittest.main()
