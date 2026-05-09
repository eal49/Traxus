"""
Headless audio test client for Traxus E2E audio verification.

Runs as a subprocess with --role sender|receiver.  No Textual dependency.
Reuses production PeerManager, MicTrack, RemoteAudioSink unchanged.

Usage:
  python tests/audio_client.py --role sender   --channel testvc --username alice
  python tests/audio_client.py --role receiver --channel testvc --username bob --output /tmp/recv.raw
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.message_types import C2S, S2C, VERSION

log = logging.getLogger("audio_client")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

_SAMPLERATE = 16_000
_BLOCKSIZE  = 320   # 20 ms per frame


# ── Tone generation ───────────────────────────────────────────────────────────

def _gen_tone_frames(freq: float = 440.0, n_frames: int = 100) -> list[bytes]:
    """Return n_frames of 20-ms int16 PCM at the given frequency."""
    import numpy as np
    frames = []
    for i in range(n_frames):
        t = np.linspace(
            i * _BLOCKSIZE / _SAMPLERATE,
            (i + 1) * _BLOCKSIZE / _SAMPLERATE,
            _BLOCKSIZE,
            endpoint=False,
        )
        samples = (np.sin(2.0 * math.pi * freq * t) * 26214.0).astype(np.int16)
        frames.append(samples.tobytes())
    return frames


# ── sounddevice mocking ───────────────────────────────────────────────────────

def _patch_mic_input() -> patch:
    """Patch client.mic_track.sd so InputStream is a no-op MagicMock."""
    p = patch("client.mic_track.sd")
    mock_sd = p.start()
    mock_sd.InputStream.return_value = MagicMock()
    return p


def _make_capture_stream(captured_chunks: list[bytes]) -> MagicMock:
    """Return a MagicMock OutputStream whose write() appends int16 PCM bytes."""
    out = MagicMock()
    out.write.side_effect = lambda data: captured_chunks.append(bytes(data))
    return out


# ── WebSocket helpers ─────────────────────────────────────────────────────────

async def _send(ws, payload: dict) -> None:
    await ws.send(json.dumps(payload))


async def auth_and_join(ws, username: str, channel: str) -> tuple[list[dict], list[dict]]:
    """
    Authenticate, create the voice channel (idempotent), and join it.

    Returns (users, pending_msgs) where:
      users        — list of users from the first voice_state that includes us
      pending_msgs — any non-voice_state messages that arrived while we were
                     waiting (e.g. voice_offer from a fast peer); these must be
                     replayed through the signaling loop before reading the socket.
    """
    await _send(ws, {"type": C2S.AUTH, "username": username, "version": VERSION})

    async for raw in ws:
        msg = json.loads(raw)
        if msg["type"] == S2C.AUTH_OK:
            log.info("[%s] auth_ok", username)
            break
        if msg["type"] == S2C.AUTH_ERROR:
            raise RuntimeError(f"auth_error: {msg}")

    # Create voice channel — channel_exists error is silently ignored
    await _send(ws, {"type": C2S.CREATE, "channel": channel, "channel_type": "voice"})
    await _send(ws, {"type": C2S.VOICE_JOIN, "channel": channel})

    # Drain messages until voice_state includes us; stash everything else so
    # the signaling loop can replay it (avoids dropping early voice_offer msgs).
    pending: list[dict] = []
    async for raw in ws:
        msg = json.loads(raw)
        if msg["type"] == S2C.VOICE_STATE and msg.get("channel") == channel:
            users = msg.get("users", [])
            if any(u["username"] == username for u in users):
                log.info(
                    "[%s] voice_state received, peers=%s",
                    username,
                    [u["username"] for u in users if u["username"] != username],
                )
                # Include this voice_state in pending so the signaling loop can
                # act on it (e.g. alice calls connect("bob") after seeing both).
                pending.append(msg)
                return users, pending
        else:
            pending.append(msg)


# ── Signaling loop ────────────────────────────────────────────────────────────

async def _dispatch(msg: dict, pm, local_username: str) -> None:
    """Route one server message to the correct PeerManager method."""
    t = msg.get("type", "")

    if t == S2C.VOICE_STATE:
        users = msg.get("users", [])
        for u in users:
            remote = u["username"]
            if remote == local_username:
                continue
            if local_username < remote and remote not in pm._peers:
                log.info("[%s] sending offer → %s", local_username, remote)
                asyncio.get_running_loop().create_task(pm.connect(remote))

    elif t == S2C.VOICE_OFFER:
        from_user = msg.get("from_user", "")
        log.info("[%s] received offer from %s", local_username, from_user)
        asyncio.get_running_loop().create_task(
            pm.on_offer(from_user, msg.get("sdp", ""))
        )

    elif t == S2C.VOICE_ANSWER:
        from_user = msg.get("from_user", "")
        log.info("[%s] received answer from %s", local_username, from_user)
        asyncio.get_running_loop().create_task(
            pm.on_answer(from_user, msg.get("sdp", ""))
        )

    elif t == S2C.VOICE_ICE:
        asyncio.get_running_loop().create_task(
            pm.on_ice(
                msg.get("from_user", ""),
                msg.get("candidate"),
                msg.get("sdpMid", "0"),
                msg.get("sdpMLineIndex", 0),
            )
        )


async def run_signaling_loop(
    ws,
    pm,
    local_username: str,
    done_event: asyncio.Event,
    pending_msgs: list[dict] | None = None,
) -> None:
    """
    Dispatch voice signaling to pm.  Replays any buffered messages first
    (those that arrived during auth_and_join before the loop was ready).
    """
    # Replay messages that arrived before PeerManager was created
    for msg in (pending_msgs or []):
        await _dispatch(msg, pm, local_username)

    try:
        async for raw in ws:
            if done_event.is_set():
                break
            await _dispatch(json.loads(raw), pm, local_username)
    except Exception as exc:
        if not done_event.is_set():
            log.warning("[%s] signaling loop: %s", local_username, exc)


# ── WsAdapter ─────────────────────────────────────────────────────────────────

class _WsAdapter:
    """
    Thin shim so PeerManager.enqueue() sends JSON over the live WebSocket.
    Must be constructed from within a running asyncio coroutine.
    """

    def __init__(self, ws) -> None:
        self._ws = ws
        self._loop = asyncio.get_running_loop()

    def enqueue(self, payload: dict) -> None:
        # Called from aiortc event-loop callbacks — schedule as a task.
        self._loop.create_task(self._ws.send(json.dumps(payload)))


# ── Sender ────────────────────────────────────────────────────────────────────

async def sender_main(args) -> None:
    mic_patch = _patch_mic_input()
    try:
        import websockets
        from aiortc import RTCConfiguration
        from client.mic_track import MicTrack
        from client.peer_manager import PeerManager

        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        async with websockets.connect(args.server) as ws:
            _, pending = await auth_and_join(ws, args.username, args.channel)

            mic        = MicTrack(loop)
            out_stream = MagicMock()   # sender doesn't play back
            from client.audio_mixer import AudioMixer
            mixer = AudioMixer(out_stream)
            pm = PeerManager(
                mic_track=mic,
                mixer=mixer,
                ws_worker=_WsAdapter(ws),
                stun_url="",
            )
            pm._config = RTCConfiguration(iceServers=[])

            sig_task = loop.create_task(
                run_signaling_loop(ws, pm, args.username, done, pending)
            )

            log.info("[%s] waiting %gs for ICE…", args.username, args.ice_wait)
            await asyncio.sleep(args.ice_wait)

            frames = _gen_tone_frames(freq=args.freq, n_frames=args.frames)
            mic.set_transmitting(True)
            # Pace injection at 20ms intervals, matching the real sounddevice
            # callback rate.  Without pacing the queue (maxsize=20) overflows
            # and MicTrack's pacing logic still only delivers 20 frames total.
            start = loop.time()
            for i, frame_bytes in enumerate(frames):
                mic._enqueue_safe(frame_bytes)
                target = start + (i + 1) * 0.020
                delay = target - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
            log.info("[%s] injected %d frames", args.username, len(frames))

            await asyncio.sleep(args.audio_wait)
            done.set()
            sig_task.cancel()
            await pm.close_all()

        log.info("[%s] sender done", args.username)
    finally:
        mic_patch.stop()


# ── Receiver ─────────────────────────────────────────────────────────────────

async def receiver_main(args) -> None:
    captured: list[bytes] = []
    mic_patch = _patch_mic_input()
    try:
        import websockets
        from aiortc import RTCConfiguration
        from client.mic_track import MicTrack
        from client.peer_manager import PeerManager

        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        async with websockets.connect(args.server) as ws:
            _, pending = await auth_and_join(ws, args.username, args.channel)

            mic        = MicTrack(loop)
            out_stream = _make_capture_stream(captured)
            from client.audio_mixer import AudioMixer
            mixer = AudioMixer(out_stream)
            pm = PeerManager(
                mic_track=mic,
                mixer=mixer,
                ws_worker=_WsAdapter(ws),
                stun_url="",
            )
            pm._config = RTCConfiguration(iceServers=[])

            sig_task = loop.create_task(
                run_signaling_loop(ws, pm, args.username, done, pending)
            )

            total = args.ice_wait + args.audio_wait + args.buffer_wait
            log.info("[%s] listening for %gs…", args.username, total)
            await asyncio.sleep(total)

            done.set()
            sig_task.cancel()
            await pm.close_all()

        raw = b"".join(captured)
        with open(args.output, "wb") as f:
            f.write(raw)
        log.info("[%s] wrote %d bytes → %s", args.username, len(raw), args.output)

    finally:
        mic_patch.stop()


# ── Entry point ───────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="Headless Traxus audio test client")
    p.add_argument("--role",        required=True, choices=["sender", "receiver"])
    p.add_argument("--channel",     default="testvc")
    p.add_argument("--username",    required=True)
    p.add_argument("--output",      default="/tmp/traxus_recv.raw")
    p.add_argument("--server",      default="ws://localhost:8765")
    p.add_argument("--frames",      type=int,   default=100)
    p.add_argument("--freq",        type=float, default=440.0)
    p.add_argument("--ice-wait",    type=float, default=3.0, dest="ice_wait")
    p.add_argument("--audio-wait",  type=float, default=2.0, dest="audio_wait")
    p.add_argument("--buffer-wait", type=float, default=2.0, dest="buffer_wait")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.role == "sender":
        asyncio.run(sender_main(args))
    else:
        asyncio.run(receiver_main(args))
