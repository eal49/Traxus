"""
AudioEngine — microphone capture and VAD for the Traxus client.

In the WebRTC pipeline, audio capture for transmission is handled by MicTrack
(aiortc AudioStreamTrack).  AudioEngine retains responsibility for:
  • VAD-mode mic listening and energy callbacks
  • Graceful degradation when sounddevice/numpy are unavailable

Graceful degradation: if sounddevice or numpy are unavailable,
AUDIO_AVAILABLE is set to False and all AudioEngine methods are no-ops.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("traxus.audio")

try:
    import numpy as np
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    np = None   # type: ignore[assignment]
    sd = None   # type: ignore[assignment]

try:
    import aiortc as _aiortc  # noqa: F401
    WEBRTC_AVAILABLE: bool = AUDIO_AVAILABLE
except ImportError:
    WEBRTC_AVAILABLE = False

_SAMPLERATE = 16_000
_CHANNELS   = 1
_DTYPE      = "int16"
_BLOCKSIZE  = 320          # samples per capture callback


class AudioEngine:
    """Manages microphone capture for VAD mode.

    In the WebRTC pipeline actual PTT audio capture and transmission is
    handled by MicTrack / PeerManager.  AudioEngine remains responsible
    for VAD-mode mic listening and energy callbacks.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None

        # VAD state
        self._vad_active: bool = False
        self._vad_threshold: float = 250.0
        self._vad_callback = None          # callable(is_voice: bool) | None
        self._vad_voice_state: bool = False
        self._energy_callback = None       # callable(rms: float) | None
        self._spectrum_callback = None     # callable(pcm_bytes: bytes) | None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(
        self,
        loop: asyncio.AbstractEventLoop,
        device: "str | None" = None,
    ) -> None:
        """Store the asyncio loop and open the microphone input stream.
        Idempotent: no-op if the stream is already open."""
        if not AUDIO_AVAILABLE:
            return
        self._loop = loop
        if self._stream is not None:
            return
        kwargs: dict = dict(
            samplerate=_SAMPLERATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=_BLOCKSIZE,
            callback=self._input_callback,
        )
        if device is not None:
            kwargs["device"] = device
        try:
            self._stream = sd.InputStream(**kwargs)
        except Exception:
            kwargs.pop("device", None)
            self._stream = sd.InputStream(**kwargs)
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

    def start_vad(
        self,
        loop: asyncio.AbstractEventLoop,
        threshold: float,
        callback,
        device: "str | None" = None,
    ) -> None:
        """Open the mic stream for VAD mode and register the voice/silence callback."""
        if not AUDIO_AVAILABLE:
            return
        self._vad_threshold = threshold
        self._vad_callback = callback
        self._vad_voice_state = False
        self._vad_active = True
        self.start(loop, device=device)  # idempotent

    def stop_vad(self) -> None:
        """Stop VAD mode and close the mic stream."""
        if not AUDIO_AVAILABLE:
            return
        self._vad_active = False
        self._vad_callback = None
        self._energy_callback = None
        self._spectrum_callback = None
        self.stop()

    def set_energy_callback(self, cb) -> None:
        """Register a callback fired with the raw RMS float on every audio frame."""
        self._energy_callback = cb

    def set_spectrum_callback(self, cb) -> None:
        """Register a callback fired with raw PCM bytes on every captured frame."""
        self._spectrum_callback = cb

    # ── Capture ───────────────────────────────────────────────────────────────

    def _compute_rms(self, indata) -> float:
        """Return the RMS energy of indata as a float."""
        return float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))

    def _detect_voice(self, indata) -> bool:
        """Return True if RMS energy of indata exceeds the VAD threshold."""
        return self._compute_rms(indata) >= self._vad_threshold

    def _input_callback(self, indata, frames, time_info, status) -> None:
        """Called by sounddevice in its audio thread (VAD mode only)."""
        if self._loop is not None and (self._vad_active or self._energy_callback is not None):
            rms = self._compute_rms(indata)
            if self._vad_active and self._vad_callback is not None:
                is_voice = rms >= self._vad_threshold
                if is_voice != self._vad_voice_state:
                    self._vad_voice_state = is_voice
                    self._loop.call_soon_threadsafe(self._vad_callback, is_voice)
            if self._energy_callback is not None:
                self._loop.call_soon_threadsafe(self._energy_callback, rms)

        # Spectrum callback for visualisation (e.g. MicTestScreen).
        if self._spectrum_callback is not None and self._loop is not None:
            pcm_bytes = indata.tobytes()
            self._loop.call_soon_threadsafe(self._spectrum_callback, pcm_bytes)
