"""
End-to-end audio pipeline latency test (LAN / loopback).

Measures the round-trip latency from the moment a packed audio frame is placed
on the sender's _binary_send_queue to the moment the receiver's AudioEngine.play()
is invoked with the decoded payload.

Topology:
    sender WsWorker  →  server (subprocess)  →  receiver WsWorker
    inject frame t0                              play() called t1
    latency = t1 - t0

Assertions (LAN / loopback conditions):
    median < 15 ms
    p95    < 30 ms
    p99    < 50 ms
    0 frames dropped  (all 50 injected frames reach play())
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.audio_engine import AudioEngine, CODEC_RAW
from client.ws_worker import WsWorker
from shared import voice_protocol
from shared.message_types import C2S, S2C, VERSION

_SERVER_URL = "ws://localhost:8765"
_CHANNEL    = "latency-test"
_FRAME_COUNT = 50
_PCM_SILENCE = b"\x00\x00" * 320  # 320 int16 samples of silence


class _MockApp:
    """Minimal app stub — captures server messages in an asyncio Queue."""

    def __init__(self) -> None:
        self._q: asyncio.Queue = asyncio.Queue()

    def post_message(self, msg) -> None:
        self._q.put_nowait(msg)

    async def wait_for(self, msg_type: str, timeout: float = 5.0) -> dict:
        """Block until a ServerMessage with the given type arrives."""
        from client.app import TraxusApp
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {msg_type!r}")
            msg = await asyncio.wait_for(self._q.get(), timeout=remaining)
            if isinstance(msg, TraxusApp.ServerMessage):
                if msg.payload.get("type") == msg_type:
                    return msg.payload


class TestAudioPipelineLatency(unittest.IsolatedAsyncioTestCase):
    """LAN latency: median < 15 ms, p95 < 30 ms, p99 < 50 ms, 0 drops."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)  # let the server bind its port

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        cls._server.wait(timeout=5)

    async def _connect_client(self, username: str) -> tuple[WsWorker, AudioEngine, _MockApp, asyncio.Task]:
        """Connect a WsWorker+AudioEngine pair, authenticate, create+join the voice channel."""
        mock_app = _MockApp()
        engine = AudioEngine()
        worker = WsWorker(mock_app, audio_engine=engine)

        task = asyncio.ensure_future(worker.run(_SERVER_URL, username))

        # Wait for auth_ok
        payload = await mock_app.wait_for("auth_ok", timeout=5.0)
        worker.notify_auth_ok()

        # Create the voice channel (idempotent — server ignores if it exists)
        worker.enqueue({
            "type": C2S.CREATE,
            "channel": _CHANNEL,
            "channel_type": "voice",
        })
        await asyncio.sleep(0.2)

        # Join the voice channel
        worker.enqueue({"type": C2S.VOICE_JOIN, "channel": _CHANNEL})
        await mock_app.wait_for("voice_state", timeout=5.0)

        return worker, engine, mock_app, task

    async def test_lan_pipeline_latency(self) -> None:
        """50 frames, measure t_play - t_enqueue; assert latency and zero drops."""
        received_times: list[float] = []
        enqueue_times: list[float] = []

        # ── Receiver ────────────────────────────────────────────────────────────
        recv_worker, recv_engine, _, recv_task = await self._connect_client("recv_bot")

        # Patch play() to record arrival timestamp
        original_play = recv_engine.play

        def _spy_play(audio_bytes: bytes, codec: int = CODEC_RAW, username: str = "") -> None:
            received_times.append(time.perf_counter())
            original_play(audio_bytes, codec, username)

        recv_engine.play = _spy_play

        # ── Sender ──────────────────────────────────────────────────────────────
        send_worker, send_engine, _, send_task = await self._connect_client("send_bot")

        # Small pause to let both clients settle in the channel
        await asyncio.sleep(0.1)

        # ── Inject 50 frames ────────────────────────────────────────────────────
        packed = voice_protocol.pack_c2s(_CHANNEL, _PCM_SILENCE, CODEC_RAW)
        for _ in range(_FRAME_COUNT):
            enqueue_times.append(time.perf_counter())
            send_worker._binary_send_queue.put_nowait(packed)
            await asyncio.sleep(0.022)  # ~22 ms inter-frame gap (one frame every 20 ms + jitter)

        # Wait up to 3 s for all frames to arrive
        deadline = time.monotonic() + 3.0
        while len(received_times) < _FRAME_COUNT and time.monotonic() < deadline:
            await asyncio.sleep(0.05)

        # ── Cleanup ─────────────────────────────────────────────────────────────
        send_worker.stop()
        recv_worker.stop()
        recv_engine._play_queue.put_nowait(None)  # shut down playback thread
        send_engine._play_queue.put_nowait(None)
        await asyncio.sleep(0.2)
        send_task.cancel()
        recv_task.cancel()
        try:
            await send_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await recv_task
        except (asyncio.CancelledError, Exception):
            pass

        # ── Latency calculations ────────────────────────────────────────────────
        n_received = len(received_times)
        n_sent = len(enqueue_times)

        # 6.5: zero frames dropped
        self.assertEqual(
            n_received,
            _FRAME_COUNT,
            f"Expected {_FRAME_COUNT} frames but received {n_received} "
            f"(dropped {_FRAME_COUNT - n_received})",
        )

        latencies_ms = [
            (received_times[i] - enqueue_times[i]) * 1000
            for i in range(n_received)
        ]
        latencies_sorted = sorted(latencies_ms)

        median_ms = statistics.median(latencies_ms)
        p95_ms = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        p99_ms = latencies_sorted[int(len(latencies_sorted) * 0.99)]

        print(
            f"\nLATENCY  median={median_ms:.1f}ms  p95={p95_ms:.1f}ms  p99={p99_ms:.1f}ms"
        )

        # 6.4: latency assertions
        self.assertLess(
            median_ms, 15.0,
            f"Median latency {median_ms:.1f}ms exceeds 15 ms — pipeline too slow",
        )
        self.assertLess(
            p95_ms, 30.0,
            f"p95 latency {p95_ms:.1f}ms exceeds 30 ms — tail latency too high",
        )
        self.assertLess(
            p99_ms, 50.0,
            f"p99 latency {p99_ms:.1f}ms exceeds 50 ms — worst-case tail too high",
        )


if __name__ == "__main__":
    unittest.main()
