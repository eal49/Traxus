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

if AUDIO_AVAILABLE:
    from shared.adpcm import CODEC_ADPCM, CODEC_RAW, decode as _adpcm_decode, encode as _adpcm_encode
    ADPCM_AVAILABLE = True
else:
    CODEC_RAW    = 0  # type: ignore[assignment]
    CODEC_ADPCM  = 1  # type: ignore[assignment]
    ADPCM_AVAILABLE = False
    _adpcm_encode = None  # type: ignore[assignment]
    _adpcm_decode = None  # type: ignore[assignment]

# Noise suppression uses only numpy (already required for ADPCM), so
# NS_AVAILABLE tracks the same condition as AUDIO_AVAILABLE.
NS_AVAILABLE: bool = AUDIO_AVAILABLE


if AUDIO_AVAILABLE:
    class _SpectralNoiseSuppressor:
        """
        Real-time single-channel spectral-subtraction noise suppressor.

        BACKGROUND
        ----------
        Spectral subtraction (Boll, 1979) is the classic algorithm for
        single-channel noise reduction in voice applications.  The core
        insight: if we can estimate the *power spectrum of the noise alone*,
        we can subtract it from the power spectrum of the noisy signal to
        recover an approximation of the clean speech.

        ALGORITHM — step by step
        ------------------------
        We process one 20 ms PCM frame (320 samples at 16 kHz) at a time.

        1. Real FFT
           rfft(x)  →  X[k],  k = 0 … N/2
           Because the input x is real-valued, the spectrum is conjugate-
           symmetric; rfft exploits this and returns only the N/2+1 unique
           complex bins instead of the full N bins.  For N=320 we get 161
           bins covering 0 Hz … 8 kHz.

        2. Signal power spectrum
           P_x[k] = |X[k]|²  =  Re(X[k])² + Im(X[k])²
           Units: (ADC counts)².  No windowing is applied; a rectangular
           window is implicit.  At 320 samples the time-bandwidth product
           is already fine for voice intelligibility.

        3. Noise model update (self-supervised)
           We can't know the noise spectrum a priori, so we adapt online.
           On every frame we decide: voice or noise?

             SNR_global = mean(P_x) / mean(N̂)

           If SNR_global < SNR_VOICE_THRESHOLD (~5 dB) the frame is
           probably noise-only and we update the noise estimate quickly:

             N̂[k]  ←  α_fast · P_x[k]  +  (1−α_fast) · N̂[k]

           If a voice signal is present (SNR_global ≥ threshold) we still
           update, but very slowly, to track long-term drift (fan speed
           changes, temperature, etc.):

             N̂[k]  ←  α_slow · P_x[k]  +  (1−α_slow) · N̂[k]

           The Exponential Moving Average (EMA) is the discrete equivalent
           of a first-order IIR low-pass filter with time constant:
             τ  =  −1 / (frame_rate · ln(1−α))
           At 50 fps, α_fast=0.15 → τ ≈ 260 ms (tracks a fan spinning up).
                      α_slow=0.005 → τ ≈ 4 s   (long-term drift only).

        4. Spectral subtraction with floor
           Subtract OVER_SUBTRACTION × noise estimate from signal power.
           Over-subtraction (α_sub > 1) compensates for estimation error
           and makes suppression more aggressive at the cost of more
           "musical noise" if over-done.

             P_y[k] = max(  P_x[k] − α_sub · N̂[k],
                             β       · P_x[k]          )

           The floor term β · P_x[k] prevents any bin from being driven to
           zero.  Complete silence in a narrow band sounds like a hole or
           click; keeping β=0.05 (−13 dB relative to original) preserves
           a natural noise floor in the output.

        5. Per-bin amplitude gain
           We want to multiply each bin's *amplitude* so that the resulting
           power equals P_y[k].  Because power ∝ amplitude²:

             G[k] = √( P_y[k] / P_x[k] )

           A small ε in the denominator prevents 0/0 at silent bins.

        6. Phase-unchanged reconstruction
           Multiply the original complex spectrum by the real gain G:

             Ŷ[k] = X[k] · G[k]

           This scales the magnitude of each bin while leaving its phase
           angle arg(X[k]) completely unchanged.  The human auditory
           system is relatively insensitive to absolute spectral phase
           (especially above ~1 kHz), so phase preservation keeps
           artifacts perceptually subtle.

        7. Inverse real FFT
           irfft(Ŷ, n=N)  →  ŷ[n],  n = 0 … N−1
           The n=N argument is explicit to guard against an off-by-one
           when N is odd (our N=320 is even, but defensive is good).

        8. Clip and cast
           irfft can produce values slightly outside [−32768, 32767] due to
           floating-point round-trip error.  Hard-clip before casting back
           to int16.

        CONSTANTS AND THEIR RATIONALE
        ------------------------------
        OVER_SUBTRACTION = 1.5
            Subtract 1.5× the estimated noise power.  Range 1.0–2.0 is
            typical; 2.0 removes more noise but produces clearly audible
            musical-noise artifacts on impulsive (non-stationary) noise.
            1.5 is a conservative middle ground suitable for fan/AC noise.

        SPECTRAL_FLOOR = 0.05
            After subtraction, keep each bin at least 5 % of its original
            power (≈ −13 dB).  Prevents dead-silent frequency holes that
            sound unnatural.

        ALPHA_FAST = 0.15
            EMA weight during noise-dominant frames.  Time constant ≈ 260 ms
            at 50 fps — fast enough to track a laptop fan spinning up but
            not so fast that a brief noise burst permanently biases the model.

        ALPHA_SLOW = 0.005
            EMA weight during voice-dominant frames.  Time constant ≈ 4 s.
            Corrects slow thermal/humidity drift without tracking voiced
            speech into the noise estimate.

        SNR_VOICE_THRESHOLD = 3.0
            Linear power ratio (≈ 4.8 dB).  Below this the frame is treated
            as noise-only and the fast EMA applies.  Voiced speech at a
            normal distance from a microphone typically has ≥ 10 dB SNR, so
            3.0 provides comfortable margin without misfiring on whispers.
        """

        OVER_SUBTRACTION:    float = 1.5
        SPECTRAL_FLOOR:      float = 0.05
        ALPHA_FAST:          float = 0.15
        ALPHA_SLOW:          float = 0.005
        SNR_VOICE_THRESHOLD: float = 3.0

        def __init__(self, frame_size: int) -> None:
            self._frame_size = frame_size
            # rfft of N real samples gives N//2+1 unique complex bins.
            # Bin 0 = DC component (0 Hz), bin N//2 = Nyquist (8 kHz at 16 kHz sr).
            n_bins = frame_size // 2 + 1
            # Initialise noise estimate to a small positive floor so the very
            # first frame produces a finite (if meaningless) SNR ratio.
            self._noise_power: np.ndarray = np.full(n_bins, 1e-6, dtype=np.float64)

        def process(self, pcm: np.ndarray) -> np.ndarray:
            """
            Filter one frame of mono int16 PCM.

            Also updates the internal noise-power estimate, so this method
            should be called on *every* captured frame — not just during PTT —
            to keep the noise model warm.

            Parameters
            ----------
            pcm : ndarray, shape (frame_size,), dtype int16
                Raw PCM from the microphone (squeeze channel dim first).

            Returns
            -------
            ndarray, shape (frame_size,), dtype int16
                Noise-suppressed PCM, clipped to the int16 range.
            """
            # ── Step 1: promote to float64 for arithmetic precision ───────────
            # int16 arithmetic overflows easily; float64 gives us 15 decimal
            # digits of headroom.
            x: np.ndarray = pcm.astype(np.float64)

            # ── Step 2: Real FFT → complex spectrum X[k] ─────────────────────
            X: np.ndarray = np.fft.rfft(x)       # shape: (n_bins,), complex128

            # ── Step 3: Signal power spectrum P_x[k] = |X[k]|² ──────────────
            P_x: np.ndarray = X.real ** 2 + X.imag ** 2   # shape: (n_bins,)

            # ── Step 4: Voice-or-noise decision ──────────────────────────────
            # Compare mean signal power to mean noise estimate.
            # +1e-10 prevents division by zero on the very first frame.
            snr_global: float = float(np.mean(P_x)) / (float(np.mean(self._noise_power)) + 1e-10)
            alpha: float = self.ALPHA_SLOW if snr_global >= self.SNR_VOICE_THRESHOLD else self.ALPHA_FAST

            # ── Step 5: Update noise estimate (EMA) ──────────────────────────
            # N̂[k] ← α · P_x[k] + (1−α) · N̂[k]
            self._noise_power = alpha * P_x + (1.0 - alpha) * self._noise_power

            # ── Step 6: Spectral subtraction with floor ───────────────────────
            # P_y[k] = max( P_x[k] − α_sub·N̂[k],  β·P_x[k] )
            P_y: np.ndarray = np.maximum(
                P_x - self.OVER_SUBTRACTION * self._noise_power,
                self.SPECTRAL_FLOOR * P_x,
            )

            # ── Step 7: Per-bin amplitude gain G[k] = √(P_y[k] / P_x[k]) ────
            G: np.ndarray = np.sqrt(P_y / np.maximum(P_x, 1e-10))

            # ── Step 8: Apply gain, preserve phase ───────────────────────────
            # Ŷ[k] = X[k] · G[k]  →  |Ŷ[k]| = |X[k]|·G[k],  arg(Ŷ[k]) = arg(X[k])
            Y: np.ndarray = X * G

            # ── Step 9: Inverse real FFT → cleaned time domain ───────────────
            # n=self._frame_size is explicit: irfft default returns 2*(M−1)
            # samples which equals frame_size when frame_size is even (320 is),
            # but being explicit avoids subtle bugs on odd frame sizes.
            y: np.ndarray = np.fft.irfft(Y, n=self._frame_size)

            # ── Step 10: Clip and cast back to int16 ─────────────────────────
            return np.clip(y, -32768, 32767).astype(np.int16)

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
        self._queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()   # (codec, audio) capture frames
        self._transmitting: bool = False

        # Spectral noise suppressor (None when NS_AVAILABLE is False)
        self._suppressor: _SpectralNoiseSuppressor | None = (
            _SpectralNoiseSuppressor(_BLOCKSIZE) if NS_AVAILABLE else None
        )
        self.noise_suppression_enabled: bool = True

        # Per-user playback volume (integer %, 0–200, default 100)
        self._per_user_volume: dict[str, int] = {}

        # VAD state
        self._vad_active: bool = False
        self._vad_threshold: float = 250.0
        self._vad_callback = None          # callable(is_voice: bool) | None
        self._vad_voice_state: bool = False  # last reported VAD state
        self._energy_callback = None       # callable(rms: float) | None
        self._spectrum_callback = None     # callable(pcm_bytes: bytes) | None

        # Loopback: route captured audio to the playback queue (mic test mode)
        self.loopback_enabled: bool = False

        # Playback: a thread-safe queue drained by a background thread.
        # Items are (codec, audio_bytes, username) tuples; None is the shutdown sentinel.
        self._play_queue: queue.Queue[tuple[int, bytes, str] | None] = queue.Queue(
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
        """Store the asyncio loop and open the microphone input stream.
        Idempotent: no-op if the stream is already open."""
        if not AUDIO_AVAILABLE:
            return
        self._loop = loop
        if self._stream is not None:
            return
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

    def start_vad(
        self,
        loop: asyncio.AbstractEventLoop,
        threshold: float,
        callback,
    ) -> None:
        """Open the mic stream for VAD mode and register the voice/silence callback."""
        if not AUDIO_AVAILABLE:
            return
        self._vad_threshold = threshold
        self._vad_callback = callback
        self._vad_voice_state = False
        self._vad_active = True
        self.start(loop)  # idempotent

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

    def set_loopback(self, enabled: bool) -> None:
        """Enable or disable mic loopback to the playback queue."""
        self.loopback_enabled = enabled

    # ── PTT state ─────────────────────────────────────────────────────────────

    @property
    def transmitting(self) -> bool:
        return self._transmitting

    @transmitting.setter
    def transmitting(self, value: bool) -> None:
        self._transmitting = value

    # ── Per-user volume ────────────────────────────────────────────────────────

    def get_volume(self, username: str) -> int:
        """Return the playback volume for username as an integer percentage (0–200)."""
        return self._per_user_volume.get(username, 100)

    def set_volume(self, username: str, level: int) -> None:
        """Set playback volume for username, clamped to [0, 200]."""
        self._per_user_volume[username] = max(0, min(200, level))

    # ── Capture ───────────────────────────────────────────────────────────────

    def _compute_rms(self, indata) -> float:
        """Return the RMS energy of indata as a float."""
        return float(np.sqrt(np.mean(np.square(indata.astype(np.float32)))))

    def _detect_voice(self, indata) -> bool:
        """Return True if RMS energy of indata exceeds the VAD threshold."""
        return self._compute_rms(indata) >= self._vad_threshold

    def _input_callback(self, indata, frames, time_info, status) -> None:
        """Called by sounddevice in its audio thread."""
        if self._loop is not None and (self._vad_active or self._energy_callback is not None):
            rms = self._compute_rms(indata)
            if self._vad_active and self._vad_callback is not None:
                is_voice = rms >= self._vad_threshold
                if is_voice != self._vad_voice_state:
                    self._vad_voice_state = is_voice
                    self._loop.call_soon_threadsafe(self._vad_callback, is_voice)
            if self._energy_callback is not None:
                self._loop.call_soon_threadsafe(self._energy_callback, rms)

        # Run spectral NS on every frame — even when not transmitting — so the
        # noise model stays warm and is ready the moment PTT is pressed.
        # indata has shape (frame_size, 1) from sounddevice; squeeze to (frame_size,).
        # Cost: ~0.3 ms per frame at 50 fps ≈ 1.5 % CPU — acceptable.
        if self._suppressor is not None and self._loop is not None and self.noise_suppression_enabled:
            pcm_filtered = self._suppressor.process(indata[:, 0])
        else:
            pcm_filtered = None   # NS unavailable or disabled; fall back to raw bytes below

        # Resolve the "best" PCM bytes for this frame (NS-filtered or raw).
        if pcm_filtered is not None:
            pcm_bytes = pcm_filtered.tobytes()
        else:
            pcm_bytes = indata.tobytes()

        # Loopback: route captured audio straight to the playback queue.
        if self.loopback_enabled and self._loop is not None:
            self._loop.call_soon_threadsafe(
                self._play_queue.put_nowait, (CODEC_RAW, pcm_bytes, "")
            )

        # Spectrum callback for visualisation (e.g. MicTestScreen).
        if self._spectrum_callback is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._spectrum_callback, pcm_bytes)

        if self._transmitting and self._loop is not None:
            if ADPCM_AVAILABLE:
                audio_bytes = _adpcm_encode(pcm_bytes)
                codec = CODEC_ADPCM
            else:
                audio_bytes = pcm_bytes
                codec = CODEC_RAW
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, (codec, audio_bytes)
            )

    async def capture_loop(self, channel: str, send_fn) -> None:
        """Drain the capture queue and send each frame via send_fn."""
        while self._transmitting:
            try:
                codec, audio_bytes = await asyncio.wait_for(self._queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            await send_fn(channel, audio_bytes, codec)

    # ── Playback ──────────────────────────────────────────────────────────────

    def play(self, audio_bytes: bytes, codec: int = CODEC_RAW, username: str = "") -> None:
        """Queue audio for playback.  Returns instantly — never blocks.

        ADPCM decode happens in the background playback thread, not here,
        so this method only does a queue.put_nowait() and returns in nanoseconds.
        username is forwarded to the playback worker for per-user gain lookup.
        """
        if not AUDIO_AVAILABLE:
            return
        try:
            self._play_queue.put_nowait((codec, audio_bytes, username))
        except queue.Full:
            # Playback thread is behind; drop the oldest frame and enqueue new.
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._play_queue.put_nowait((codec, audio_bytes, username))
            except queue.Full:
                pass  # give up if still full

    def _playback_worker(self) -> None:
        """
        Background thread: owns a single continuous OutputStream and writes
        PCM frames to it as they arrive.  One stream, no per-frame stop/start.
        ADPCM decode happens here so play() never blocks the Textual pump.
        """
        try:
            with sd.OutputStream(
                samplerate=_SAMPLERATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
            ) as out_stream:
                while True:
                    item = self._play_queue.get()
                    if item is None:             # sentinel → shut down
                        break
                    codec, audio_bytes, username = item
                    if ADPCM_AVAILABLE and codec == CODEC_ADPCM:
                        pcm_bytes = _adpcm_decode(audio_bytes)
                    else:
                        pcm_bytes = audio_bytes
                    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
                    level = self._per_user_volume.get(username, 100)
                    if level != 100:
                        audio = np.clip(
                            audio.astype(np.float32) * (level / 100.0),
                            -32768, 32767,
                        ).astype(np.int16)
                    out_stream.write(audio)
        except Exception:
            log.exception("Playback worker crashed")
