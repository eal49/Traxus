"""
MicTrack — bridges sounddevice InputStream to an aiortc AudioStreamTrack.

The sounddevice callback fires every 20 ms in the audio thread and puts raw
PCM frames into a thread-safe asyncio.Queue via call_soon_threadsafe.  The
aiortc pipeline calls recv() asynchronously to pull those frames.  When PTT
is inactive, recv() yields silence so the WebRTC connection stays up.
"""
from __future__ import annotations

import asyncio
import fractions
import logging

log = logging.getLogger("traxus.mic_track")

try:
    import numpy as np
    import sounddevice as sd
    import av
    from aiortc import AudioStreamTrack
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    AudioStreamTrack = object  # type: ignore[assignment,misc]

_SAMPLERATE = 16_000
_CHANNELS   = 1
_BLOCKSIZE  = 320          # 20 ms per frame
_DTYPE      = "int16"
_QUEUE_MAX  = 20           # drop oldest beyond this to avoid memory growth


class MicTrack(AudioStreamTrack):
    """
    Live microphone source for aiortc.

    Public interface:
      set_transmitting(bool)  — gate real vs. silence output
      stop()                  — close the InputStream
    """

    kind = "audio"

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._loop = loop
        self._transmitting: bool = False

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._pts: int = 0
        self._start: float | None = None  # wall-clock origin for pacing

        self._stream = sd.InputStream(
            samplerate=_SAMPLERATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=_BLOCKSIZE,
            callback=self._input_callback,
        )
        self._stream.start()

    # ── PTT gate ──────────────────────────────────────────────────────────────

    def set_transmitting(self, enabled: bool) -> None:
        self._transmitting = enabled

    # ── sounddevice callback (audio thread) ───────────────────────────────────

    def _input_callback(self, indata, frames, time_info, status) -> None:
        if not self._transmitting:
            return

        raw = indata[:, 0].tobytes()
        self._loop.call_soon_threadsafe(self._enqueue_safe, raw)

    def _enqueue_safe(self, raw: bytes) -> None:
        try:
            self._queue.put_nowait(raw)
        except asyncio.QueueFull:
            pass  # consumer is lagging; drop frame to avoid blocking the event loop

    # ── aiortc AudioStreamTrack interface ─────────────────────────────────────

    async def recv(self) -> "av.AudioFrame":
        # Pace delivery to one frame per 20 ms (real-time rate).
        # Without this aiortc polls recv() thousands of times per second,
        # draining the queue instantly and filling the stream with silence.
        loop = asyncio.get_running_loop()
        if self._start is None:
            self._start = loop.time()
        target = self._start + self._pts / _SAMPLERATE
        wait = target - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)

        try:
            raw = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            raw = None  # no real frame — send silence

        if raw is not None:
            samples = np.frombuffer(raw, dtype=np.int16)
        else:
            samples = np.zeros(_BLOCKSIZE, dtype=np.int16)

        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1),  # (channels, samples)
            format="s16",
            layout="mono",
        )
        frame.sample_rate = _SAMPLERATE
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, _SAMPLERATE)
        self._pts += _BLOCKSIZE
        return frame

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def stop(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        super().stop()
