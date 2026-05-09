"""
Unit tests for client/mic_track.py.

Tests:
  - MicTrack.recv() returns silence frames when not transmitting
  - MicTrack.recv() returns real audio frames when transmitting
  - Frame shape (320 samples) and pts sequencing
  - _input_callback transmit gate
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


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicTrackDevice(unittest.IsolatedAsyncioTestCase):

    async def test_device_param_passed_to_input_stream(self):
        """MicTrack.__init__ with device='My Mic' passes device= to sd.InputStream."""
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop, device="My Mic")
            track.stop()
        call_kwargs = mock_cls.call_args_list[0][1]
        self.assertEqual(call_kwargs.get("device"), "My Mic")

    async def test_no_device_param_when_none(self):
        """MicTrack.__init__ with device=None does not pass device= to sd.InputStream."""
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop, device=None)
            track.stop()
        # device should not be in kwargs (or be None if present)
        call_kwargs = mock_cls.call_args_list[0][1]
        self.assertNotIn("device", call_kwargs)

    async def test_restart_stream_swaps_stream(self):
        """restart_stream() stops old stream and opens a new one."""
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        stream_a = MagicMock()
        stream_b = MagicMock()
        calls = [stream_a, stream_b]
        with patch("sounddevice.InputStream", side_effect=calls):
            track = MicTrack(loop)
            old_stream = track._stream
            track.restart_stream("New Device")
            track.stop()
        self.assertIs(old_stream, stream_a)
        self.assertIs(track._stream, stream_b)
        self.assertIsNot(track._stream, old_stream)

    async def test_restart_stream_falls_back_on_error(self):
        """restart_stream() falls back to system default if device not found."""
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("device") == "Bad Device":
                raise ValueError("device not found")
            return MagicMock()

        with patch("sounddevice.InputStream", side_effect=side_effect):
            track = MicTrack(loop)  # call 1 (no device)
            track.restart_stream("Bad Device")  # call 2 fails, call 3 fallback
            track.stop()

        # call 1: init (no device), call 2: Bad Device (raises), call 3: fallback (no device)
        self.assertEqual(call_count, 3)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestMicFork(unittest.IsolatedAsyncioTestCase):
    """MicFork — independent fan-out branch of MicTrack."""

    async def test_fork_returns_mic_fork_instance(self):
        from client.mic_track import MicFork, MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            track.stop()
        self.assertIsInstance(fork, MicFork)

    async def test_fork_queue_registered_in_mic_track(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            self.assertIn(fork._queue, track._fork_queues)
            track.stop()

    async def test_unfork_removes_queue(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            track.unfork(fork)
            self.assertNotIn(fork._queue, track._fork_queues)
            track.stop()

    async def test_enqueue_safe_fans_out_to_fork(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            raw = np.ones(320, dtype=np.int16).tobytes()
            track._enqueue_safe(raw)
            track.stop()
        self.assertFalse(fork._queue.empty())
        self.assertEqual(fork._queue.get_nowait(), raw)

    async def test_fork_recv_returns_queued_pcm(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            track.stop()
        pcm = (np.ones(320, dtype=np.int16) * 500).tobytes()
        await fork._queue.put(pcm)
        frame = await fork.recv()
        arr = frame.to_ndarray().flatten()
        self.assertEqual(arr[0], 500)

    async def test_fork_recv_returns_silence_when_empty(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            track.stop()
        frame = await fork.recv()
        arr = frame.to_ndarray()
        self.assertTrue((arr == 0).all())

    async def test_multiple_forks_each_receive_frames(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork_a = track.fork()
            fork_b = track.fork()
            raw = np.ones(320, dtype=np.int16).tobytes()
            track._enqueue_safe(raw)
            track.stop()
        self.assertFalse(fork_a._queue.empty(), "fork_a must receive frame")
        self.assertFalse(fork_b._queue.empty(), "fork_b must receive frame")

    async def test_unfork_stops_frame_delivery(self):
        from client.mic_track import MicTrack
        loop = asyncio.get_running_loop()
        with patch("sounddevice.InputStream") as mock_cls:
            mock_cls.return_value = MagicMock()
            track = MicTrack(loop)
            fork = track.fork()
            track.unfork(fork)
            raw = np.ones(320, dtype=np.int16).tobytes()
            track._enqueue_safe(raw)
            track.stop()
        self.assertTrue(fork._queue.empty(), "unfork'd fork must not receive frames")


if __name__ == "__main__":
    unittest.main()
