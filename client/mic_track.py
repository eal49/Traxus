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

# Import NS suppressor lazily to avoid circular dependency with audio_engine
try:
    from client.audio_engine import _SpectralNoiseSuppressor, NS_AVAILABLE
except ImportError:
    _SpectralNoiseSuppressor = None  # type: ignore[assignment,misc]
    NS_AVAILABLE = False


class MicTrack(AudioStreamTrack):
    """
    Live microphone source for aiortc.

    Public interface:
      set_transmitting(bool)  — gate real vs. silence output
      noise_suppression_enabled — read/write bool
      stop()                  — close the InputStream
    """

    kind = "audio"

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._loop = loop
        self._transmitting: bool = False
        self.noise_suppression_enabled: bool = True

        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._pts: int = 0
        self._suppressor = (
            _SpectralNoiseSuppressor(_BLOCKSIZE)
            if NS_AVAILABLE and _SpectralNoiseSuppressor is not None
            else None
        )

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
        pcm = indata[:, 0]  # shape (320,) int16

        if self._suppressor is not None and self.noise_suppression_enabled:
            pcm = self._suppressor.process(pcm)

        # Always keep the noise model warm; only enqueue when transmitting.
        if not self._transmitting:
            return

        raw = pcm.tobytes()
        self._loop.call_soon_threadsafe(self._enqueue_safe, raw)

    def _enqueue_safe(self, raw: bytes) -> None:
        try:
            self._queue.put_nowait(raw)
        except asyncio.QueueFull:
            pass  # consumer is lagging; drop frame to avoid blocking the event loop

    # ── aiortc AudioStreamTrack interface ─────────────────────────────────────

    async def recv(self) -> "av.AudioFrame":
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
