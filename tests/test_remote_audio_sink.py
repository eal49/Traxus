"""
Unit tests for client/remote_audio_sink.py.

Tests:
  - Volume gain is applied correctly at levels other than 100
  - 100% volume leaves PCM unchanged (fast path)
  - Graceful exit when track raises MediaStreamError
  - Writes go through the out_stream_holder[0] reference
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import numpy as np
    import av
    import aiortc  # noqa: F401
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False


def _make_frame(samples: np.ndarray) -> "av.AudioFrame":
    """Build an av.AudioFrame from a 1D int16 array."""
    frame = av.AudioFrame.from_ndarray(
        samples.reshape(1, -1), format="s16", layout="mono"
    )
    frame.sample_rate = 16000
    return frame


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkVolumeGain(unittest.IsolatedAsyncioTestCase):
    """Volume gain is applied to outgoing PCM."""

    def _make_sink(self, volume_level: int, username: str = "alice"):
        from client.remote_audio_sink import RemoteAudioSink
        track = MagicMock()
        out_stream = MagicMock()
        out_stream.write = MagicMock()
        holder = [out_stream]
        volume_dict = {username: volume_level}
        return RemoteAudioSink(track, username, holder, volume_dict), track, out_stream

    async def test_100_percent_leaves_pcm_unchanged(self):
        sink, track, out_stream = self._make_sink(100)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        written = out_stream.write.call_args[0][0]
        np.testing.assert_array_equal(written, pcm)

    async def test_50_percent_halves_amplitude(self):
        sink, track, out_stream = self._make_sink(50)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        written = out_stream.write.call_args[0][0]
        expected = np.clip(pcm.astype(np.float32) * 0.5, -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(written, expected)

    async def test_200_percent_doubles_amplitude(self):
        sink, track, out_stream = self._make_sink(200)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        written = out_stream.write.call_args[0][0]
        expected = np.clip(pcm.astype(np.float32) * 2.0, -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(written, expected)

    async def test_zero_volume_gives_silence(self):
        sink, track, out_stream = self._make_sink(0)
        pcm = np.ones(320, dtype=np.int16) * 5000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        written = out_stream.write.call_args[0][0]
        self.assertTrue((written == 0).all(), "Volume=0 must produce silence")


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkExit(unittest.IsolatedAsyncioTestCase):
    """Graceful exit when the track ends."""

    async def test_exits_cleanly_on_media_stream_error(self):
        from client.remote_audio_sink import RemoteAudioSink

        track = MagicMock()
        track.recv = AsyncMock(side_effect=aiortc.mediastreams.MediaStreamError())
        out_stream = MagicMock()
        sink = RemoteAudioSink(track, "bob", [out_stream], {})

        try:
            await asyncio.wait_for(sink.run(), timeout=2.0)
        except asyncio.TimeoutError:
            self.fail("run() did not exit on MediaStreamError")

    async def test_multiple_frames_before_track_end(self):
        from client.remote_audio_sink import RemoteAudioSink

        pcm = np.zeros(320, dtype=np.int16)
        frames = [_make_frame(pcm) for _ in range(3)]

        async def recv():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track = MagicMock()
        track.recv = AsyncMock(side_effect=recv)
        out_stream = MagicMock()
        sink = RemoteAudioSink(track, "alice", [out_stream], {})
        await sink.run()

        self.assertEqual(out_stream.write.call_count, 3)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkHolder(unittest.IsolatedAsyncioTestCase):
    """Writes go through holder[0], so swapping the holder swaps the target stream."""

    async def test_write_goes_to_holder_zero(self):
        """Writes should call holder[0].write, not a stored stream reference."""
        from client.remote_audio_sink import RemoteAudioSink

        pcm = np.ones(320, dtype=np.int16) * 500
        frames = [_make_frame(pcm)]

        async def recv():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track = MagicMock()
        track.recv = AsyncMock(side_effect=recv)
        stream_a = MagicMock()
        holder = [stream_a]
        sink = RemoteAudioSink(track, "alice", holder, {})
        await sink.run()

        self.assertTrue(stream_a.write.called)

    async def test_write_follows_swapped_holder(self):
        """After swapping holder[0], writes go to the new stream."""
        from client.remote_audio_sink import RemoteAudioSink

        pcm = np.ones(320, dtype=np.int16) * 500
        frames = [_make_frame(pcm), _make_frame(pcm)]

        stream_a = MagicMock()
        stream_b = MagicMock()
        holder = [stream_a]

        call_count = 0

        async def recv():
            nonlocal call_count
            if frames:
                call_count += 1
                f = frames.pop(0)
                if call_count == 1:
                    # Swap AFTER first frame is returned so first write goes to stream_a,
                    # second write goes to stream_b.
                    holder[0] = stream_b
                return f
            raise aiortc.mediastreams.MediaStreamError()

        track = MagicMock()
        track.recv = AsyncMock(side_effect=recv)
        sink = RemoteAudioSink(track, "alice", holder, {})
        await sink.run()

        self.assertTrue(stream_b.write.called, "second frame should go to stream_b after swap")


if __name__ == "__main__":
    unittest.main()
