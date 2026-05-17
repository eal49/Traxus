"""
Unit tests for client/audio_mixer.py.

Tests:
  - No users → mixer writes a silence frame each tick
  - Single user → mixer output equals that user's pushed frame
  - Two users → mixer output equals float32 sum clipped to int16
  - Two users where sum exceeds int16 range → output is clipped
  - User slot with no queued frame → mixer fills with silence, does not stall
  - add_user then remove_user → removed user's frames no longer appear
  - close() cancels the internal task cleanly, no exception raised
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def _make_stream():
    """Return a mock OutputStream whose write() records each call."""
    stream = MagicMock()
    stream.write = MagicMock()
    return stream


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerSilence(unittest.IsolatedAsyncioTestCase):
    """With no users, the mixer writes a zeroed frame every 20 ms."""

    async def test_no_users_writes_silence(self):
        from client.audio_mixer import AudioMixer, _DEFAULT_FRAME_SIZE

        stream = _make_stream()
        mixer = AudioMixer(stream)
        try:
            # Wait for at least one tick (20 ms) plus a little margin
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        self.assertGreater(stream.write.call_count, 0, "mixer must write at least once")
        written = stream.write.call_args[0][0]
        self.assertEqual(len(written), _DEFAULT_FRAME_SIZE)
        self.assertTrue((written == 0).all(), "no-user output must be silence")


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerSingleUser(unittest.IsolatedAsyncioTestCase):
    """Single user's pushed frame passes through unchanged (volume 100 applied outside)."""

    async def test_single_user_frame_passes_through(self):
        from client.audio_mixer import AudioMixer, _GLOBAL_RECV_GAIN

        pcm = np.ones(960, dtype=np.int16) * 1000
        expected = np.clip(
            pcm.astype(np.float32) * _GLOBAL_RECV_GAIN, -32768, 32767
        ).astype(np.int16)
        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        try:
            mixer.push("alice", pcm)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        # Find the write call that contains non-silence
        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0, "no non-silent frame was written")
        np.testing.assert_array_equal(audio_writes[0], expected)


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerTwoUsers(unittest.IsolatedAsyncioTestCase):
    """Two users' frames are summed correctly."""

    async def test_two_users_summed(self):
        from client.audio_mixer import AudioMixer, _GLOBAL_RECV_GAIN

        pcm_a = np.ones(960, dtype=np.int16) * 1000
        pcm_b = np.ones(960, dtype=np.int16) * 500
        expected = np.clip(
            (pcm_a.astype(np.float32) + pcm_b.astype(np.float32)) * _GLOBAL_RECV_GAIN,
            -32768, 32767,
        ).astype(np.int16)

        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.add_user("bob")
        try:
            mixer.push("alice", pcm_a)
            mixer.push("bob", pcm_b)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0, "no non-silent frame was written")
        np.testing.assert_array_equal(audio_writes[0], expected)

    async def test_two_users_sum_clipped(self):
        from client.audio_mixer import AudioMixer

        # Both at max int16 → sum would overflow without clipping
        pcm_a = np.full(960, 32767, dtype=np.int16)
        pcm_b = np.full(960, 32767, dtype=np.int16)
        expected = np.full(960, 32767, dtype=np.int16)

        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.add_user("bob")
        try:
            mixer.push("alice", pcm_a)
            mixer.push("bob", pcm_b)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0)
        np.testing.assert_array_equal(audio_writes[0], expected)


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerMissingFrame(unittest.IsolatedAsyncioTestCase):
    """If a user has no queued frame, the mixer fills with silence and does not stall."""

    async def test_missing_frame_does_not_stall(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.add_user("bob")
        try:
            # Only push for alice; bob contributes silence
            mixer.push("alice", np.ones(960, dtype=np.int16) * 800)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        # Mixer must have written without stalling
        self.assertGreater(stream.write.call_count, 0)

    async def test_missing_frame_contributes_silence(self):
        from client.audio_mixer import AudioMixer, _GLOBAL_RECV_GAIN

        pcm_a = np.ones(960, dtype=np.int16) * 800
        # bob has no frame — should contribute zeros; gain still applied to alice's frame
        expected = np.clip(
            pcm_a.astype(np.float32) * _GLOBAL_RECV_GAIN, -32768, 32767
        ).astype(np.int16)

        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.add_user("bob")
        try:
            mixer.push("alice", pcm_a)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0)
        np.testing.assert_array_equal(audio_writes[0], expected)


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerSlotManagement(unittest.IsolatedAsyncioTestCase):
    """add_user / remove_user update the active slot set correctly."""

    async def test_removed_user_frames_not_mixed(self):
        from client.audio_mixer import AudioMixer

        pcm = np.ones(960, dtype=np.int16) * 1000
        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.push("alice", pcm)
        mixer.remove_user("alice")
        try:
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        # All writes should be silence since alice was removed before the tick
        for call in stream.write.call_args_list:
            written = call[0][0]
            self.assertTrue(
                (written == 0).all(),
                "alice's frame appeared after remove_user",
            )

    async def test_push_after_remove_is_noop(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        mixer.remove_user("alice")
        try:
            # push() on a removed user must not raise and must not affect output
            mixer.push("alice", np.ones(960, dtype=np.int16) * 500)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        for call in stream.write.call_args_list:
            written = call[0][0]
            self.assertTrue((written == 0).all())


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerClose(unittest.IsolatedAsyncioTestCase):
    """close() cancels the internal task cleanly and stops the stream."""

    async def test_close_no_exception(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        try:
            await mixer.close()  # must not raise
        except Exception as exc:
            self.fail(f"close() raised {exc!r}")

    async def test_close_cancels_task(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        task_before = mixer._task
        self.assertIsNotNone(task_before)
        await mixer.close()
        self.assertIsNone(mixer._task, "mixer._task must be None after close()")
        self.assertTrue(task_before.done(), "internal task must be done after close()")

    async def test_close_when_no_users(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        try:
            await mixer.close()
        except Exception as exc:
            self.fail(f"close() with empty slot map raised {exc!r}")

    async def test_double_close_safe(self):
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        await mixer.close()
        try:
            await mixer.close()  # second close must not raise
        except Exception as exc:
            self.fail(f"second close() raised {exc!r}")


@unittest.skipUnless(NUMPY_AVAILABLE, "numpy not available")
class TestAudioMixerGlobalGain(unittest.IsolatedAsyncioTestCase):
    """_GLOBAL_RECV_GAIN is applied to all mixed output before clip."""

    async def test_global_gain_doubles_amplitude(self):
        from client.audio_mixer import AudioMixer, _GLOBAL_RECV_GAIN

        # Use an amplitude small enough that 2× stays within int16 range
        amplitude = 4000
        pcm = np.full(960, amplitude, dtype=np.int16)
        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        try:
            mixer.push("alice", pcm)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0, "no non-silent frame written")
        expected_amplitude = int(amplitude * _GLOBAL_RECV_GAIN)
        self.assertTrue(
            (audio_writes[0] == expected_amplitude).all(),
            f"expected all samples = {expected_amplitude}, got {audio_writes[0][:4]}…",
        )

    async def test_global_gain_clips_at_int16_max(self):
        """Gain must not produce values outside int16 range."""
        from client.audio_mixer import AudioMixer

        pcm = np.full(960, 32767, dtype=np.int16)
        stream = _make_stream()
        mixer = AudioMixer(stream)
        mixer.add_user("alice")
        try:
            mixer.push("alice", pcm)
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        audio_writes = [
            call[0][0] for call in stream.write.call_args_list
            if not (call[0][0] == 0).all()
        ]
        self.assertGreater(len(audio_writes), 0)
        self.assertTrue(
            (audio_writes[0] == 32767).all(),
            "clipping must prevent overflow above int16 max",
        )

    async def test_silence_unaffected_by_gain(self):
        """Silence (all zeros) stays zero regardless of gain."""
        from client.audio_mixer import AudioMixer

        stream = _make_stream()
        mixer = AudioMixer(stream)
        try:
            await asyncio.sleep(0.040)
        finally:
            await mixer.close()

        for call in stream.write.call_args_list:
            self.assertTrue(
                (call[0][0] == 0).all(),
                "silence frame must remain all-zeros after gain",
            )


if __name__ == "__main__":
    unittest.main()
