"""
AudioMixer — single-writer software mixer for remote voice participants.

One instance lives per voice session, owned by PeerManager.
Each remote participant gets a queue slot via add_user(); their
RemoteAudioSink pushes decoded int16 PCM into it.  The internal _run()
task wakes every 20 ms, sums all queued frames as float32, clips to
int16, and performs exactly one sd.OutputStream.write() call per tick.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

log = logging.getLogger("traxus.mixer")

if TYPE_CHECKING:
    import numpy as np
    import sounddevice as sd

_FRAME_DURATION = 0.020    # 20 ms per tick
_DEFAULT_FRAME_SIZE = 960  # samples at 48 kHz; updated from first real frame
_QUEUE_MAX = 20


class AudioMixer:
    """
    Owns the sd.OutputStream and is the sole writer to it.

    Must be constructed from an async context (a running event loop is
    required for asyncio.ensure_future at construction time).
    """

    def __init__(self, out_stream: "sd.OutputStream") -> None:
        self._stream_holder: list = [out_stream]
        self._queues: dict[str, asyncio.Queue] = {}
        self._frame_size: int = _DEFAULT_FRAME_SIZE
        self._task: asyncio.Task | None = asyncio.ensure_future(self._run())

    # ── Slot management ───────────────────────────────────────────────────────

    def add_user(self, username: str) -> None:
        if username not in self._queues:
            self._queues[username] = asyncio.Queue(maxsize=_QUEUE_MAX)

    def remove_user(self, username: str) -> None:
        self._queues.pop(username, None)

    # ── Push interface for RemoteAudioSink ────────────────────────────────────

    def push(self, username: str, pcm: "np.ndarray") -> None:
        q = self._queues.get(username)
        if q is None:
            return
        self._frame_size = len(pcm)
        try:
            q.put_nowait(pcm)
        except asyncio.QueueFull:
            pass  # sink is ahead of the mixer tick; drop oldest-equivalent

    # ── Mixer loop ────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        import numpy as np
        loop = asyncio.get_running_loop()
        start = loop.time()
        tick = 0
        while True:
            tick += 1
            target = start + tick * _FRAME_DURATION
            wait = target - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)

            frame_size = self._frame_size
            mixed = np.zeros(frame_size, dtype=np.float32)
            for q in list(self._queues.values()):
                try:
                    frame = q.get_nowait()
                    mixed += frame.astype(np.float32)
                except asyncio.QueueEmpty:
                    pass  # this user has no frame this tick; contribute silence

            out = np.clip(mixed, -32768, 32767).astype(np.int16)
            stream = self._stream_holder[0]
            try:
                await loop.run_in_executor(None, stream.write, out)
            except Exception:
                pass  # stream swapped or stopped; frame dropped

    # ── Output device hot-swap ────────────────────────────────────────────────

    def restart_output_stream(self, device: "str | None") -> None:
        """Atomically replace the OutputStream with one on the given device.

        Open new → swap holder → wait one frame budget → close old.
        This avoids a Pa_StopStream / Pa_WriteStream race on Windows WASAPI.
        """
        import time
        import sounddevice as sd
        old_stream = self._stream_holder[0]
        kwargs: dict = dict(samplerate=48000, channels=1, dtype="int16", latency=0.08)
        if device is not None:
            kwargs["device"] = device
        try:
            new_stream = sd.OutputStream(**kwargs)
        except Exception:
            kwargs.pop("device", None)
            new_stream = sd.OutputStream(**kwargs)
        new_stream.start()
        self._stream_holder[0] = new_stream
        time.sleep(0.060)
        try:
            old_stream.stop()
            old_stream.close()
        except Exception:
            pass

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._queues.clear()
        stream = self._stream_holder[0]
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
