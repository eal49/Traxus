"""
Unit tests for client/peer_manager.py.

Uses mocked RTCPeerConnection, AudioMixer, and WsWorker.
Tests:
  - connect() creates PC, adds MicTrack, sends voice_offer, calls mixer.add_user
  - on_offer() answers incoming offer, sends voice_answer, calls mixer.add_user
  - on_answer() sets remote description on existing PC
  - on_ice() adds ICE candidate to existing PC
  - disconnect() closes PC, cancels sink task, calls mixer.remove_user
  - close_all() closes all PCs, stops MicTrack, calls mixer.close
  - restart_output_stream() delegates to mixer
  - ICE candidate events send voice_ice via WsWorker
"""
from __future__ import annotations

import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import aiortc  # noqa: F401
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False

from shared.message_types import C2S


def _make_mock_pc():
    """Build a minimal mock RTCPeerConnection."""
    pc = MagicMock()
    pc.addTrack = MagicMock()
    pc.close = AsyncMock()
    pc.createOffer = AsyncMock(return_value=MagicMock(sdp="offer-sdp", type="offer"))
    pc.createAnswer = AsyncMock(return_value=MagicMock(sdp="answer-sdp", type="answer"))
    pc.setLocalDescription = AsyncMock()
    pc.setRemoteDescription = AsyncMock()
    pc.addIceCandidate = AsyncMock()
    pc.localDescription = MagicMock(sdp="local-sdp")
    pc._ice_handlers = []

    def on_event(event_name):
        def decorator(fn):
            if event_name == "icecandidate":
                pc._ice_handlers.append(fn)
            return fn
        return decorator

    pc.on = on_event
    return pc


def _make_mock_mixer():
    """Build a minimal AudioMixer mock."""
    mixer = MagicMock()
    mixer.add_user = MagicMock()
    mixer.remove_user = MagicMock()
    mixer.restart_output_stream = MagicMock()
    mixer.close = AsyncMock()
    return mixer


def _make_peer_manager(mock_pc=None):
    """Build a PeerManager with mocked dependencies."""
    if mock_pc is None:
        mock_pc = _make_mock_pc()

    mic_track = MagicMock()
    mic_track.stop = MagicMock()

    mixer = _make_mock_mixer()
    ws_worker = MagicMock()
    ws_worker.enqueue = MagicMock()

    with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
         patch("aiortc.RTCConfiguration"), \
         patch("aiortc.RTCIceServer"):
        from client.peer_manager import PeerManager
        pm = PeerManager(mic_track, mixer, ws_worker, stun_url="stun:test")

    return pm, mic_track, ws_worker, mock_pc, mixer


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPeerManagerConnect(unittest.IsolatedAsyncioTestCase):

    async def test_connect_sends_voice_offer(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        ws_worker.enqueue.assert_called_once()
        sent = ws_worker.enqueue.call_args[0][0]
        self.assertEqual(sent["type"], C2S.VOICE_OFFER)
        self.assertEqual(sent["to_user"], "bob")
        self.assertIn("sdp", sent)

    async def test_connect_adds_mic_fork(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        mic_track.fork.assert_called_once()
        mock_pc.addTrack.assert_called_once_with(mic_track.fork.return_value)

    async def test_connect_stores_peer(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        self.assertIn("bob", pm._peers)

    async def test_connect_calls_mixer_add_user(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        mixer.add_user.assert_called_once_with("bob")

    async def test_connect_idempotent_on_duplicate(self):
        mock_pc = _make_mock_pc()
        pm, _, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")
            await pm.connect("bob")  # second call should be a no-op

        self.assertEqual(ws_worker.enqueue.call_count, 1)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPeerManagerOnOffer(unittest.IsolatedAsyncioTestCase):

    async def test_on_offer_sends_voice_answer(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
             patch("aiortc.RTCSessionDescription"):
            await pm.on_offer("alice", "offer-sdp")

        ws_worker.enqueue.assert_called_once()
        sent = ws_worker.enqueue.call_args[0][0]
        self.assertEqual(sent["type"], C2S.VOICE_ANSWER)
        self.assertEqual(sent["to_user"], "alice")

    async def test_on_offer_sets_remote_description(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
             patch("aiortc.RTCSessionDescription") as MockSDP:
            MockSDP.return_value = MagicMock()
            await pm.on_offer("alice", "offer-sdp")

        mock_pc.setRemoteDescription.assert_awaited_once()

    async def test_on_offer_creates_answer(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
             patch("aiortc.RTCSessionDescription"):
            await pm.on_offer("alice", "offer-sdp")

        mock_pc.createAnswer.assert_awaited_once()

    async def test_on_offer_calls_mixer_add_user(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
             patch("aiortc.RTCSessionDescription"):
            await pm.on_offer("alice", "offer-sdp")

        mixer.add_user.assert_called_once_with("alice")

    async def test_on_offer_adds_mic_fork(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc), \
             patch("aiortc.RTCSessionDescription"):
            await pm.on_offer("alice", "offer-sdp")

        mic_track.fork.assert_called_once()
        mock_pc.addTrack.assert_called_once_with(mic_track.fork.return_value)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPeerManagerOnAnswer(unittest.IsolatedAsyncioTestCase):

    async def test_on_answer_sets_remote_description(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        pm._peers["bob"] = mock_pc

        with patch("aiortc.RTCSessionDescription") as MockSDP:
            MockSDP.return_value = MagicMock()
            await pm.on_answer("bob", "answer-sdp")

        mock_pc.setRemoteDescription.assert_awaited_once()

    async def test_on_answer_no_op_for_unknown_peer(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCSessionDescription"):
            await pm.on_answer("nobody", "sdp")  # must not raise

        mock_pc.setRemoteDescription.assert_not_awaited()


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPeerManagerDisconnect(unittest.IsolatedAsyncioTestCase):

    async def test_disconnect_closes_pc(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)
        pm._peers["bob"] = mock_pc

        await pm.disconnect("bob")

        mock_pc.close.assert_awaited_once()
        self.assertNotIn("bob", pm._peers)

    async def test_disconnect_calls_mixer_remove_user(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)
        pm._peers["bob"] = mock_pc

        await pm.disconnect("bob")

        mixer.remove_user.assert_called_once_with("bob")

    async def test_disconnect_calls_unfork(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, _, _, mixer = _make_peer_manager(mock_pc)

        # Simulate a connected peer with a registered fork
        fake_fork = MagicMock()
        pm._peers["bob"] = mock_pc
        pm._forks["bob"] = fake_fork

        await pm.disconnect("bob")

        mic_track.unfork.assert_called_once_with(fake_fork)
        self.assertNotIn("bob", pm._forks)

    async def test_disconnect_no_op_for_unknown_peer(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        await pm.disconnect("nobody")  # must not raise
        mock_pc.close.assert_not_awaited()

    async def test_close_all_closes_every_peer(self):
        mock_pc1 = _make_mock_pc()
        mock_pc2 = _make_mock_pc()
        pm, mic_track, _, _, mixer = _make_peer_manager(mock_pc1)
        pm._peers = {"alice": mock_pc1, "bob": mock_pc2}

        await pm.close_all()

        mock_pc1.close.assert_awaited_once()
        mock_pc2.close.assert_awaited_once()
        self.assertEqual(len(pm._peers), 0)

    async def test_close_all_stops_mic_track(self):
        mock_pc = _make_mock_pc()
        pm, mic_track, _, _, mixer = _make_peer_manager(mock_pc)

        await pm.close_all()

        mic_track.stop.assert_called_once()

    async def test_close_all_calls_mixer_close(self):
        mock_pc = _make_mock_pc()
        pm, _, _, _, mixer = _make_peer_manager(mock_pc)

        await pm.close_all()

        mixer.close.assert_awaited_once()

    async def test_restart_output_stream_delegates_to_mixer(self):
        pm, _, _, _, mixer = _make_peer_manager()

        pm.restart_output_stream("my-device")

        mixer.restart_output_stream.assert_called_once_with("my-device")


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPeerManagerVolume(unittest.IsolatedAsyncioTestCase):

    async def test_default_volume_100(self):
        pm, _, _, _, mixer = _make_peer_manager()
        self.assertEqual(pm.get_volume("alice"), 100)

    async def test_set_and_get_volume(self):
        pm, _, _, _, mixer = _make_peer_manager()
        pm.set_volume("alice", 75)
        self.assertEqual(pm.get_volume("alice"), 75)

    async def test_volume_clamped_to_200(self):
        pm, _, _, _, mixer = _make_peer_manager()
        pm.set_volume("alice", 300)
        self.assertEqual(pm.get_volume("alice"), 200)

    async def test_volume_clamped_to_0(self):
        pm, _, _, _, mixer = _make_peer_manager()
        pm.set_volume("alice", -10)
        self.assertEqual(pm.get_volume("alice"), 0)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestIceCandidateEvent(unittest.IsolatedAsyncioTestCase):

    async def test_ice_candidate_event_enqueues_voice_ice(self):
        mock_pc = _make_mock_pc()
        pm, _, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        candidate = MagicMock()
        candidate.to_sdp.return_value = "1 1 UDP 123 192.168.1.1 50000 typ host"
        candidate.sdpMid = "audio"
        candidate.sdpMLineIndex = 0

        for handler in mock_pc._ice_handlers:
            handler(candidate)

        ws_worker.enqueue.assert_called()
        calls = ws_worker.enqueue.call_args_list
        ice_calls = [c for c in calls if c[0][0].get("type") == C2S.VOICE_ICE]
        self.assertEqual(len(ice_calls), 1)
        ice_payload = ice_calls[0][0][0]
        self.assertEqual(ice_payload["to_user"], "bob")
        self.assertIn("candidate", ice_payload)

    async def test_null_ice_candidate_not_sent(self):
        mock_pc = _make_mock_pc()
        pm, _, ws_worker, _, mixer = _make_peer_manager(mock_pc)

        with patch("aiortc.RTCPeerConnection", return_value=mock_pc):
            await pm.connect("bob")

        ws_worker.enqueue.reset_mock()

        for handler in mock_pc._ice_handlers:
            handler(None)  # end-of-candidates

        ice_calls = [
            c for c in ws_worker.enqueue.call_args_list
            if c[0][0].get("type") == C2S.VOICE_ICE
        ]
        self.assertEqual(len(ice_calls), 0)


_SDP_WITH_FMTP = (
    "v=0\r\n"
    "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    "a=rtpmap:111 opus/48000/2\r\n"
    "a=fmtp:111 minptime=10\r\n"
)

_SDP_WITHOUT_FMTP = (
    "v=0\r\n"
    "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
    "a=rtpmap:111 opus/48000/2\r\n"
)

_SDP_NO_OPUS = (
    "v=0\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 96\r\n"
    "a=rtpmap:96 VP8/90000\r\n"
)


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc not available")
class TestPatchOpusSdp(unittest.TestCase):

    def setUp(self):
        from client.peer_manager import _patch_opus_sdp
        self.patch = _patch_opus_sdp

    def test_adds_dtx_fec_and_bitrate_to_existing_fmtp(self):
        result = self.patch(_SDP_WITH_FMTP)
        self.assertIn("usedtx=1", result)
        self.assertIn("useinbandfec=1", result)
        self.assertIn("maxaveragebitrate=16000", result)

    def test_preserves_existing_fmtp_params(self):
        result = self.patch(_SDP_WITH_FMTP)
        self.assertIn("minptime=10", result)

    def test_inserts_fmtp_line_when_absent(self):
        result = self.patch(_SDP_WITHOUT_FMTP)
        self.assertIn("a=fmtp:111", result)
        self.assertIn("usedtx=1", result)
        self.assertIn("useinbandfec=1", result)
        self.assertIn("maxaveragebitrate=16000", result)

    def test_no_opus_returns_sdp_unchanged(self):
        result = self.patch(_SDP_NO_OPUS)
        self.assertEqual(result, _SDP_NO_OPUS)

    def test_overwrites_existing_usedtx_value(self):
        sdp = (
            "v=0\r\n"
            "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
            "a=rtpmap:111 opus/48000/2\r\n"
            "a=fmtp:111 usedtx=0;useinbandfec=0\r\n"
        )
        result = self.patch(sdp)
        self.assertIn("usedtx=1", result)
        self.assertIn("useinbandfec=1", result)
        self.assertNotIn("usedtx=0", result)
        self.assertNotIn("useinbandfec=0", result)

    def test_fmtp_line_inserted_after_rtpmap(self):
        result = self.patch(_SDP_WITHOUT_FMTP)
        lines = result.split("\r\n")
        rtpmap_idx = next(i for i, l in enumerate(lines) if "a=rtpmap:111" in l)
        fmtp_idx = next(i for i, l in enumerate(lines) if "a=fmtp:111" in l)
        self.assertEqual(fmtp_idx, rtpmap_idx + 1)


if __name__ == "__main__":
    unittest.main()
