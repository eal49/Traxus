"""
PeerManager — manages RTCPeerConnection lifecycle for voice channels.

One PeerManager exists while the local client is in a voice channel.
It owns the MicTrack, creates/closes peer connections on join/leave events,
and routes signaling messages (offer/answer/ICE) received from the server.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from shared.message_types import C2S

log = logging.getLogger("traxus.peers")

if TYPE_CHECKING:
    import sounddevice as sd
    from aiortc import RTCPeerConnection
    from client.mic_track import MicTrack
    from client.ws_worker import WsWorker


class PeerManager:
    def __init__(
        self,
        mic_track: "MicTrack",
        out_stream: "sd.OutputStream",
        ws_worker: "WsWorker",
        stun_url: str = "stun:stun.l.google.com:19302",
    ) -> None:
        from aiortc import RTCConfiguration, RTCIceServer
        self._mic_track = mic_track
        self._out_stream = out_stream
        self._ws_worker = ws_worker
        self._config = RTCConfiguration(
            iceServers=[RTCIceServer(urls=[stun_url])]
        )
        self._peers: dict[str, RTCPeerConnection] = {}
        self._sink_tasks: dict[str, asyncio.Task] = {}
        self._volume: dict[str, int] = {}
        self._out_stream_holder: list = [out_stream]

    @property
    def mic_track(self) -> "MicTrack":
        return self._mic_track

    # ── Outgoing offer (we join an existing participant) ──────────────────────

    async def connect(self, username: str) -> None:
        """Create an RTCPeerConnection to a remote participant and send offer."""
        if username in self._peers:
            return
        pc = await self._create_pc(username)
        pc.addTrack(self._mic_track)
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        self._ws_worker.enqueue({
            "type": C2S.VOICE_OFFER,
            "to_user": username,
            "sdp": pc.localDescription.sdp,
        })
        log.debug("Sent offer to %s", username)

    # ── Incoming offer (remote joins, we answer) ──────────────────────────────

    async def on_offer(self, from_user: str, sdp: str) -> None:
        """Handle an incoming SDP offer; create answer and start sink."""
        if from_user in self._peers:
            await self._peers[from_user].close()
        pc = await self._create_pc(from_user)
        pc.addTrack(self._mic_track)

        from aiortc import RTCSessionDescription
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        self._ws_worker.enqueue({
            "type": C2S.VOICE_ANSWER,
            "to_user": from_user,
            "sdp": pc.localDescription.sdp,
        })
        log.debug("Answered offer from %s", from_user)

    # ── Incoming answer ───────────────────────────────────────────────────────

    async def on_answer(self, from_user: str, sdp: str) -> None:
        pc = self._peers.get(from_user)
        if pc is None:
            return
        from aiortc import RTCSessionDescription
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="answer"))
        log.debug("Set answer from %s", from_user)

    # ── Incoming ICE candidate ────────────────────────────────────────────────

    async def on_ice(
        self,
        from_user: str,
        candidate: str | None,
        sdp_mid: str,
        sdp_mline_index: int,
    ) -> None:
        pc = self._peers.get(from_user)
        if pc is None:
            return
        if candidate is None:
            return  # end-of-candidates signal — nothing to add
        from aiortc.sdp import candidate_from_sdp
        try:
            c = candidate_from_sdp(candidate.split("candidate:")[1])
            c.sdpMid = sdp_mid
            c.sdpMLineIndex = sdp_mline_index
            await pc.addIceCandidate(c)
        except Exception:
            log.debug("ICE candidate add failed for %s", from_user)

    # ── Disconnect a single peer ──────────────────────────────────────────────

    async def disconnect(self, username: str) -> None:
        task = self._sink_tasks.pop(username, None)
        if task:
            task.cancel()
        pc = self._peers.pop(username, None)
        if pc:
            await pc.close()
        log.debug("Disconnected peer %s", username)

    # ── Close all peers (voice leave) ─────────────────────────────────────────

    async def close_all(self) -> None:
        usernames = list(self._peers.keys())
        for username in usernames:
            await self.disconnect(username)
        self._mic_track.stop()
        try:
            self._out_stream_holder[0].stop()
            self._out_stream_holder[0].close()
        except Exception:
            pass

    # ── Output device hot-swap ────────────────────────────────────────────────

    def restart_output_stream(self, device: "str | None") -> None:
        """Replace the shared OutputStream with a new one on the given device.

        Order: open new → swap holder → wait one frame → close old.
        This avoids Pa_StopStream racing with a live Pa_WriteStream on the
        event loop thread, which causes a multi-second hang on Windows WASAPI.
        """
        import time
        import sounddevice as sd
        old_stream = self._out_stream_holder[0]
        kwargs: dict = dict(samplerate=48000, channels=1, dtype="int16", latency=0.08)
        if device is not None:
            kwargs["device"] = device
        try:
            new_stream = sd.OutputStream(**kwargs)
        except Exception:
            kwargs.pop("device", None)
            new_stream = sd.OutputStream(**kwargs)
        new_stream.start()
        # Atomic swap: RemoteAudioSink picks up new_stream on its next frame.
        self._out_stream_holder[0] = new_stream
        # Wait for any write() already in flight on old_stream to finish before
        # stopping it. write() is now in an executor and blocks ≤20 ms per frame;
        # 60 ms (3×) gives safe margin even if the event loop was slow to schedule.
        time.sleep(0.060)
        try:
            old_stream.stop()
            old_stream.close()
        except Exception:
            pass

    # ── Per-peer volume ───────────────────────────────────────────────────────

    def get_volume(self, username: str) -> int:
        return self._volume.get(username, 100)

    def set_volume(self, username: str, level: int) -> None:
        self._volume[username] = max(0, min(200, level))

    # ── Internal: create peer connection with ICE wiring ─────────────────────

    async def _create_pc(self, username: str) -> "RTCPeerConnection":
        from aiortc import RTCPeerConnection
        pc = RTCPeerConnection(configuration=self._config)
        self._peers[username] = pc

        @pc.on("icecandidate")
        def on_ice_candidate(candidate) -> None:
            if candidate is None:
                return
            self._ws_worker.enqueue({
                "type": C2S.VOICE_ICE,
                "to_user": username,
                "candidate": f"candidate:{candidate.to_sdp()}",
                "sdpMid": candidate.sdpMid or "0",
                "sdpMLineIndex": candidate.sdpMLineIndex or 0,
            })

        @pc.on("track")
        def on_track(track) -> None:
            if track.kind == "audio":
                from client.remote_audio_sink import RemoteAudioSink
                sink = RemoteAudioSink(track, username, self._out_stream_holder, self._volume)
                task = asyncio.ensure_future(sink.run())
                self._sink_tasks[username] = task

        return pc
