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
            log.debug("AudioMixer: added slot for %s (%d total)", username, len(self._queues))

    def remove_user(self, username: str) -> None:
        if self._queues.pop(username, None) is not None:
            log.debug("AudioMixer: removed slot for %s (%d remaining)", username, len(self._queues))

    # ── Push interface for RemoteAudioSink ────────────────────────────────────

    def push(self, username: str, pcm: "np.ndarray") -> None:
        q = self._queues.get(username)
        if q is None:
            log.debug("AudioMixer: push from %s ignored (no slot)", username)
            return
        self._frame_size = len(pcm)
        try:
            q.put_nowait(pcm)
        except asyncio.QueueFull:
            log.debug("AudioMixer: queue full for %s, dropping frame", username)

    # ── Mixer loop ────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        import numpy as np
        loop = asyncio.get_running_loop()
        start = loop.time()
        tick = 0
        while True:
            try:
                tick += 1
                target = start + tick * _FRAME_DURATION
                wait = target - loop.time()
                if wait > 0:
                    await asyncio.sleep(wait)

                frame_size = self._frame_size
                mixed = np.zeros(frame_size, dtype=np.float32)
                n_mixed = 0
                n_silent = 0

                for username, q in list(self._queues.items()):
                    try:
                        frame = q.get_nowait()
                        if len(frame) != frame_size:
                            # Guard against unexpected frame sizes from the codec.
                            # Truncate if too long; pad with zeros if too short.
                            log.warning(
                                "AudioMixer: frame size mismatch from %s "
                                "(expected %d, got %d) — adjusting",
                                username, frame_size, len(frame),
                            )
                            if len(frame) > frame_size:
                                frame = frame[:frame_size]
                            else:
                                frame = np.pad(frame, (0, frame_size - len(frame)))
                        mixed += frame.astype(np.float32)
                        n_mixed += 1
                    except asyncio.QueueEmpty:
                        n_silent += 1

                out = np.clip(mixed, -32768, 32767).astype(np.int16)

                if tick % 50 == 0:  # once per second
                    rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)))
                    log.debug(
                        "AudioMixer tick %d: %d mixed / %d silent, rms=%.0f",
                        tick, n_mixed, n_silent, rms,
                    )

                stream = self._stream_holder[0]
                try:
                    await loop.run_in_executor(None, stream.write, out)
                except Exception:
                    pass  # stream swapped or stopped; frame dropped

            except asyncio.CancelledError:
                raise  # let close() cancel us cleanly
            except Exception:
                log.exception("AudioMixer._run: unhandled error at tick %d — continuing", tick)

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
