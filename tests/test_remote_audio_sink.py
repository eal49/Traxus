"""
Unit tests for client/remote_audio_sink.py.

Tests:
  - Volume gain is applied correctly at levels other than 100
  - 100% volume leaves PCM unchanged (fast path)
  - Graceful exit when track raises MediaStreamError
  - push() is called on the AudioMixer with correct PCM
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

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


def _make_mixer():
    """Build a minimal AudioMixer mock."""
    mixer = MagicMock()
    mixer.push = MagicMock()
    return mixer


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkVolumeGain(unittest.IsolatedAsyncioTestCase):
    """Volume gain is applied to PCM before pushing to the mixer."""

    def _make_sink(self, volume_level: int, username: str = "alice"):
        from client.remote_audio_sink import RemoteAudioSink
        track = MagicMock()
        mixer = _make_mixer()
        volume_dict = {username: volume_level}
        return RemoteAudioSink(track, username, mixer, volume_dict), track, mixer

    async def test_100_percent_leaves_pcm_unchanged(self):
        sink, track, mixer = self._make_sink(100)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        mixer.push.assert_called_once()
        _, pushed = mixer.push.call_args[0]
        np.testing.assert_array_equal(pushed, pcm)

    async def test_50_percent_halves_amplitude(self):
        sink, track, mixer = self._make_sink(50)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        mixer.push.assert_called_once()
        _, pushed = mixer.push.call_args[0]
        expected = np.clip(pcm.astype(np.float32) * 0.5, -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(pushed, expected)

    async def test_200_percent_doubles_amplitude(self):
        sink, track, mixer = self._make_sink(200)
        pcm = np.ones(320, dtype=np.int16) * 1000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        mixer.push.assert_called_once()
        _, pushed = mixer.push.call_args[0]
        expected = np.clip(pcm.astype(np.float32) * 2.0, -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(pushed, expected)

    async def test_zero_volume_gives_silence(self):
        sink, track, mixer = self._make_sink(0)
        pcm = np.ones(320, dtype=np.int16) * 5000

        frames = [_make_frame(pcm)]

        async def recv_side_effect():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track.recv = AsyncMock(side_effect=recv_side_effect)
        await sink.run()

        mixer.push.assert_called_once()
        _, pushed = mixer.push.call_args[0]
        self.assertTrue((pushed == 0).all(), "Volume=0 must produce silence")


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkExit(unittest.IsolatedAsyncioTestCase):
    """Graceful exit when the track ends."""

    async def test_exits_cleanly_on_media_stream_error(self):
        from client.remote_audio_sink import RemoteAudioSink

        track = MagicMock()
        track.recv = AsyncMock(side_effect=aiortc.mediastreams.MediaStreamError())
        mixer = _make_mixer()
        sink = RemoteAudioSink(track, "bob", mixer, {})

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
        mixer = _make_mixer()
        sink = RemoteAudioSink(track, "alice", mixer, {})
        await sink.run()

        self.assertEqual(mixer.push.call_count, 3)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc/av/numpy not available")
class TestRemoteAudioSinkPush(unittest.IsolatedAsyncioTestCase):
    """push() is called with the correct username and PCM on each frame."""

    async def test_push_called_with_username(self):
        from client.remote_audio_sink import RemoteAudioSink

        pcm = np.ones(320, dtype=np.int16) * 500
        frames = [_make_frame(pcm)]

        async def recv():
            if frames:
                return frames.pop(0)
            raise aiortc.mediastreams.MediaStreamError()

        track = MagicMock()
        track.recv = AsyncMock(side_effect=recv)
        mixer = _make_mixer()
        sink = RemoteAudioSink(track, "alice", mixer, {})
        await sink.run()

        mixer.push.assert_called_once()
        username_arg, _ = mixer.push.call_args[0]
        self.assertEqual(username_arg, "alice")

    async def test_no_push_on_immediate_track_end(self):
        from client.remote_audio_sink import RemoteAudioSink

        track = MagicMock()
        track.recv = AsyncMock(side_effect=aiortc.mediastreams.MediaStreamError())
        mixer = _make_mixer()
        sink = RemoteAudioSink(track, "alice", mixer, {})
        await sink.run()

        mixer.push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
