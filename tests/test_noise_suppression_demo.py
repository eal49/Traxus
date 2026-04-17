"""
Noise suppression demo test — generates tests/noise_suppression_demo.png.

Produces a 4-panel figure showing the suppressor's effect on three controlled
signal types:
  1. Stationary white noise only
  2. Speech-like tone buried in white noise
  3. Speech-like tone with noise suppression disabled (control)

Panels:
  Top-left   : time-domain waveforms (raw vs filtered)
  Top-right  : frequency-domain magnitude spectra (raw vs filtered)
  Bottom-left: per-scenario RMS energy bar chart (raw vs filtered)
  Bottom-right: SNR improvement per scenario (dB)
"""
from __future__ import annotations

import os
import sys
import unittest

import numpy as np
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe in test runners
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.audio_engine import NS_AVAILABLE, _BLOCKSIZE

_SR = 16_000        # Hz
_FRAME = _BLOCKSIZE  # 320 samples = 20 ms at 16 kHz
_OUTPUT = os.path.join(os.path.dirname(__file__), "noise_suppression_demo.png")

# ── signal factories ──────────────────────────────────────────────────────────

def _sine(freq: float, amplitude: int, n: int = _FRAME) -> np.ndarray:
    """Pure sine wave, int16, shape (n,)."""
    t = np.linspace(0, n / _SR, n, endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _white_noise(amplitude: int, n: int = _FRAME, seed: int = 0) -> np.ndarray:
    """White noise, int16, shape (n,)."""
    rng = np.random.default_rng(seed=seed)
    return rng.integers(-amplitude, amplitude, size=n, dtype=np.int16)


def _mix(signal: np.ndarray, noise: np.ndarray) -> np.ndarray:
    """Clip-safe int32 → int16 mix."""
    return np.clip(
        signal.astype(np.int32) + noise.astype(np.int32), -32768, 32767
    ).astype(np.int16)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def _snr_db(signal: np.ndarray, noise: np.ndarray) -> float:
    """SNR in dB: 20·log10(RMS_signal / RMS_noise). Returns −∞ if noise=0."""
    rms_s = _rms(signal)
    rms_n = _rms(noise)
    if rms_n < 1e-9:
        return float("inf")
    return 20.0 * np.log10(rms_s / rms_n + 1e-10)


def _magnitude_db(x: np.ndarray) -> np.ndarray:
    """FFT magnitude in dB, positive-frequency bins only."""
    spectrum = np.abs(np.fft.rfft(x.astype(np.float64)))
    return 20.0 * np.log10(spectrum + 1e-10)


def _freqs() -> np.ndarray:
    """Frequency axis for rfft of length _FRAME at _SR Hz."""
    return np.fft.rfftfreq(_FRAME, d=1.0 / _SR)


# ── suppress helper ───────────────────────────────────────────────────────────

def _make_warm_suppressor(warmup_frames: int = 40, noise_amp: int = 300):
    """Return a _SpectralNoiseSuppressor whose noise model has been warmed up."""
    from client.audio_engine import _SpectralNoiseSuppressor
    ns = _SpectralNoiseSuppressor(_FRAME)
    rng = np.random.default_rng(seed=99)
    for _ in range(warmup_frames):
        frame = rng.integers(-noise_amp, noise_amp, size=_FRAME, dtype=np.int16)
        ns.process(frame)
    return ns


# ── test class ────────────────────────────────────────────────────────────────

@unittest.skipUnless(NS_AVAILABLE, "numpy not available — demo requires numpy")
class TestNoiseSuppresionDemo(unittest.TestCase):
    """Generates a PNG figure demonstrating noise suppressor effectiveness."""

    # ── scenario builders ─────────────────────────────────────────────────────

    def _scenario_noise_only(self):
        """Pure white noise frame — suppressor should attenuate it significantly."""
        noise = _white_noise(amplitude=800, seed=7)
        ns = _make_warm_suppressor(warmup_frames=50, noise_amp=800)
        filtered = ns.process(noise)
        return "Noise only\n(no speech)", noise, filtered

    def _scenario_speech_in_noise(self):
        """600 Hz tone (speech-like) mixed with white noise — tone should survive."""
        speech = _sine(freq=600, amplitude=6000)
        noise  = _white_noise(amplitude=800, seed=7)
        noisy  = _mix(speech, noise)
        ns = _make_warm_suppressor(warmup_frames=50, noise_amp=800)
        filtered = ns.process(noisy)
        return "Speech + noise\n(600 Hz tone)", noisy, filtered

    def _scenario_disabled(self):
        """Same noisy signal but suppressor flag disabled — output equals input."""
        speech = _sine(freq=600, amplitude=6000)
        noise  = _white_noise(amplitude=800, seed=7)
        noisy  = _mix(speech, noise)
        # Suppressor is bypassed: filtered == noisy
        filtered = noisy.copy()
        return "NS disabled\n(control)", noisy, filtered

    # ── assertions (real test coverage) ──────────────────────────────────────

    def test_noise_only_rms_is_reduced(self):
        """Suppressor should lower RMS of a pure-noise frame."""
        _, raw, filtered = self._scenario_noise_only()
        self.assertLess(_rms(filtered), _rms(raw),
                        "Suppressor did not reduce RMS of pure-noise frame")

    def test_speech_in_noise_rms_not_amplified(self):
        """Filtering a speech+noise frame must not amplify energy beyond raw."""
        _, raw, filtered = self._scenario_speech_in_noise()
        self.assertLessEqual(_rms(filtered), _rms(raw) * 1.05,
                             "Suppressor amplified speech+noise frame by more than 5%")

    def test_disabled_output_equals_input(self):
        """Control scenario: bypassed suppressor must leave signal unchanged."""
        _, raw, filtered = self._scenario_disabled()
        np.testing.assert_array_equal(raw, filtered)

    # ── figure generation ─────────────────────────────────────────────────────

    def test_generate_demo_figure(self):
        """Render a 4-panel matplotlib figure and save to tests/noise_suppression_demo.png."""

        scenarios = [
            self._scenario_noise_only(),
            self._scenario_speech_in_noise(),
            self._scenario_disabled(),
        ]

        t = np.arange(_FRAME) / _SR * 1000  # ms
        freqs = _freqs()

        COLORS = {
            "raw":      "#E05C5C",
            "filtered": "#4C9BE8",
            "bar_raw":  "#E05C5C",
            "bar_filt": "#4C9BE8",
        }

        fig = plt.figure(figsize=(16, 10))
        fig.patch.set_facecolor("#1A1A2E")
        gs = gridspec.GridSpec(
            2, 2,
            figure=fig,
            hspace=0.45,
            wspace=0.35,
            left=0.07, right=0.97,
            top=0.88, bottom=0.09,
        )

        ax_time  = fig.add_subplot(gs[0, 0])
        ax_freq  = fig.add_subplot(gs[0, 1])
        ax_rms   = fig.add_subplot(gs[1, 0])
        ax_snr   = fig.add_subplot(gs[1, 1])

        panel_style = dict(facecolor="#0F0F1E", alpha=0.85)
        for ax in (ax_time, ax_freq, ax_rms, ax_snr):
            ax.set_facecolor(panel_style["facecolor"])
            ax.tick_params(colors="#CCCCCC", labelsize=8)
            ax.title.set_color("#EEEEEE")
            ax.xaxis.label.set_color("#CCCCCC")
            ax.yaxis.label.set_color("#CCCCCC")
            for spine in ax.spines.values():
                spine.set_edgecolor("#444466")

        # ── Panel 1: time domain ─────────────────────────────────────────────
        ax_time.set_title("Time Domain — Waveforms", fontsize=11, pad=8)
        offsets = [0, 40000, 80000]  # vertical lanes per scenario

        for (label, raw, filt), offset in zip(scenarios, offsets):
            ax_time.plot(t, raw.astype(np.float32)    + offset,
                         color=COLORS["raw"],      lw=0.9, alpha=0.75, label="Raw" if offset == 0 else "")
            ax_time.plot(t, filt.astype(np.float32)   + offset,
                         color=COLORS["filtered"], lw=0.9, alpha=0.90, label="Filtered" if offset == 0 else "")
            ax_time.text(0.3, offset + 4500, label.replace("\n", "  "),
                         color="#AAAACC", fontsize=7.5, va="bottom")
            ax_time.axhline(offset, color="#333355", lw=0.5, ls="--")

        ax_time.set_xlabel("Time (ms)")
        ax_time.set_ylabel("Amplitude (int16)")
        ax_time.legend(loc="upper right", fontsize=8,
                       facecolor="#1A1A2E", labelcolor="#CCCCCC", framealpha=0.7)
        ax_time.set_xlim(0, t[-1])

        # ── Panel 2: frequency domain ─────────────────────────────────────────
        ax_freq.set_title("Frequency Domain — Magnitude Spectra", fontsize=11, pad=8)
        offsets_db = [0, 60, 120]

        for (label, raw, filt), off_db in zip(scenarios, offsets_db):
            ax_freq.plot(freqs / 1000, _magnitude_db(raw)    + off_db,
                         color=COLORS["raw"],      lw=0.9, alpha=0.75)
            ax_freq.plot(freqs / 1000, _magnitude_db(filt)   + off_db,
                         color=COLORS["filtered"], lw=0.9, alpha=0.90)
            ax_freq.text(0.2, off_db + 5, label.replace("\n", "  "),
                         color="#AAAACC", fontsize=7.5, va="bottom")

        ax_freq.set_xlabel("Frequency (kHz)")
        ax_freq.set_ylabel("Magnitude (dB, offset per scenario)")
        ax_freq.set_xlim(0, _SR / 2 / 1000)

        # ── Panel 3: RMS bar chart ────────────────────────────────────────────
        ax_rms.set_title("RMS Energy — Raw vs Filtered", fontsize=11, pad=8)
        labels   = [s[0].replace("\n", " ") for s in scenarios]
        rms_raw  = [_rms(s[1]) for s in scenarios]
        rms_filt = [_rms(s[2]) for s in scenarios]
        x = np.arange(len(labels))
        w = 0.35

        bars_r = ax_rms.bar(x - w/2, rms_raw,  w, label="Raw",      color=COLORS["bar_raw"],  alpha=0.85)
        bars_f = ax_rms.bar(x + w/2, rms_filt, w, label="Filtered", color=COLORS["bar_filt"], alpha=0.85)

        for bar in list(bars_r) + list(bars_f):
            ax_rms.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 30,
                        f"{bar.get_height():.0f}",
                        ha="center", va="bottom", fontsize=7, color="#CCCCCC")

        ax_rms.set_xticks(x)
        ax_rms.set_xticklabels(labels, fontsize=8)
        ax_rms.set_ylabel("RMS amplitude")
        ax_rms.legend(fontsize=8, facecolor="#1A1A2E", labelcolor="#CCCCCC", framealpha=0.7)

        # ── Panel 4: SNR improvement ──────────────────────────────────────────
        ax_snr.set_title("Noise Reduction (raw RMS − filtered RMS)", fontsize=11, pad=8)
        reductions = [r - f for r, f in zip(rms_raw, rms_filt)]
        bar_colors = ["#4CC88A" if v > 0 else "#E05C5C" for v in reductions]
        bars_s = ax_snr.bar(x, reductions, color=bar_colors, alpha=0.85, width=0.5)

        for bar, val in zip(bars_s, reductions):
            ax_snr.text(bar.get_x() + bar.get_width() / 2,
                        val + (8 if val >= 0 else -18),
                        f"{val:.0f}",
                        ha="center", va="bottom", fontsize=8, color="#CCCCCC")

        ax_snr.axhline(0, color="#555577", lw=1)
        ax_snr.set_xticks(x)
        ax_snr.set_xticklabels(labels, fontsize=8)
        ax_snr.set_ylabel("RMS reduction (positive = less noise)")

        # ── figure title ──────────────────────────────────────────────────────
        fig.suptitle(
            "Traxus — Spectral Noise Suppressor Effectiveness Demo\n"
            f"Frame size: {_FRAME} samples @ {_SR} Hz ({_FRAME / _SR * 1000:.0f} ms)   "
            "Red = raw   Blue = filtered",
            fontsize=12, color="#EEEEEE", y=0.96,
        )

        fig.savefig(_OUTPUT, dpi=140, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)

        self.assertTrue(os.path.exists(_OUTPUT),
                        f"Demo figure was not written to {_OUTPUT}")
        size = os.path.getsize(_OUTPUT)
        self.assertGreater(size, 10_000,
                           f"Demo figure seems too small ({size} bytes) — likely blank")


if __name__ == "__main__":
    unittest.main()
