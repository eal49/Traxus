"""
AudioEngine — wraps sounddevice for PTT voice capture and playback.

Graceful degradation: if sounddevice or numpy are unavailable,
AUDIO_AVAILABLE is set to False and all AudioEngine methods are no-ops.

Playback architecture
---------------------
Incoming PCM frames are put into a thread-safe queue by play() (a
nanosecond operation).  A dedicated daemon thread owns a single
sd.OutputStream and continuously writes from that queue.  This means:
  • play() never blocks the asyncio event loop
  • no per-frame stop()/start() cycles → no audio glitches
  • the Textual message pump processes audio messages instantly
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading

log = logging.getLogger("traxus.audio")

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    np = None   # type: ignore[assignment]
    sd = None   # type: ignore[assignment]

_SAMPLERATE = 16_000
_CHANNELS   = 1
_DTYPE      = "int16"
_BLOCKSIZE  = 320          # samples per capture callback
_PLAY_QUEUE_MAX = 10       # drop old frames rather than buffer unboundedly


class AudioEngine:
    """Manages microphone capture and speaker playback via sounddevice."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()   # capture frames
        self._transmitting: bool = False

        # Playback: a thread-safe queue drained by a background thread.
        self._play_queue: queue.Queue[bytes | None] = queue.Queue(
            maxsize=_PLAY_QUEUE_MAX
        )
        self._play_thread: threading.Thread | None = None
        if AUDIO_AVAILABLE:
            self._play_thread = threading.Thread(
                target=self._playback_worker, daemon=True, name="traxus-playback"
            )
            self._play_thread.start()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store the asyncio loop and open the microphone input stream."""
        if not AUDIO_AVAILABLE:
            return
        self._loop = loop
        self._stream = sd.InputStream(
            samplerate=_SAMPLERATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=_BLOCKSIZE,
            callback=self._input_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop the microphone input stream and clear the loop reference."""
        if not AUDIO_AVAILABLE:
            return
        self._loop = None
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ── PTT state ─────────────────────────────────────────────────────────────

    @property
    def transmitting(self) -> bool:
        return self._transmitting

    @transmitting.setter
    def transmitting(self, value: bool) -> None:
        self._transmitting = value

    # ── Capture ───────────────────────────────────────────────────────────────

    def _input_callback(self, indata, frames, time_info, status) -> None:
        """Called by sounddevice in its audio thread."""
        if self._transmitting and self._loop is not None:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, indata.tobytes()
            )

    async def capture_loop(self, channel: str, send_fn) -> None:
        """Drain the PCM queue and send each frame via send_fn."""
        while self._transmitting:
            try:
                pcm_bytes = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            await send_fn(channel, pcm_bytes)

    # ── Playback ──────────────────────────────────────────────────────────────

    def play(self, pcm_bytes: bytes) -> None:
        """Queue PCM bytes for playback.  Returns instantly — never blocks."""
        if not AUDIO_AVAILABLE:
            return
        try:
            self._play_queue.put_nowait(pcm_bytes)
        except queue.Full:
            # Playback thread is behind; drop the oldest frame and enqueue new.
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._play_queue.put_nowait(pcm_bytes)
            except queue.Full:
                pass  # give up if still full

    def _playback_worker(self) -> None:
        """
        Background thread: owns a single continuous OutputStream and writes
        PCM frames to it as they arrive.  One stream, no per-frame stop/start.
        """
        try:
            with sd.OutputStream(
                samplerate=_SAMPLERATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
            ) as out_stream:
                while True:
                    pcm_bytes = self._play_queue.get()
                    if pcm_bytes is None:        # sentinel → shut down
                        break
                    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
                    out_stream.write(audio)
        except Exception:
            log.exception("Playback worker crashed")
