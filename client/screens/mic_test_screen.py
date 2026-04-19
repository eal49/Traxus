"""
MicTestScreen — live mic loopback + spectrogram + level bar.

Opens the microphone, plays captured (NS-filtered) audio back through the
speakers so the user hears what they sound like to others, and displays a
rolling ASCII spectrogram (frequency × time) plus an RMS level bar.
"""
from __future__ import annotations

import asyncio
from collections import deque

import numpy as np

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static

_SPEC_COLS = 48          # number of time columns in spectrogram
_SPEC_ROWS = 16          # number of frequency rows
_BAR_WIDTH = 40          # characters in the RMS level bar
_SAMPLERATE = 16_000
_BLOCKSIZE = 320
_INTENSITY = " ░▒▓█"     # 5 levels: silence → loud
_RMS_MAX = 1_500.0       # RMS ceiling for 100% level bar


class MicTestScreen(ModalScreen[None]):
    """Live mic test: loopback + spectrogram + level bar."""

    DEFAULT_CSS = """
    MicTestScreen {
        align: center middle;
    }
    #mic-test-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #spectrogram {
        width: 52;
        height: 18;
        border: round $accent;
        background: $surface;
        padding: 0 1;
    }
    #level-bar {
        width: 52;
        height: 1;
        margin-top: 1;
    }
    #ns-status {
        width: 52;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    #loopback-status {
        width: 52;
        text-align: center;
        margin-top: 0;
    }
    #mic-test-hint {
        width: 52;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("l",      "toggle_loopback", "Toggle loopback"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._spec_history: deque[list[str]] = deque(
            [[" "] * _SPEC_ROWS for _ in range(_SPEC_COLS)], maxlen=_SPEC_COLS
        )
        self._latest_rms: float = 0.0
        self._new_data: bool = False

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label("Microphone Test", id="mic-test-title")
        yield Static("", id="spectrogram")
        yield Static("", id="level-bar")
        yield Label("", id="ns-status")
        yield Label("", id="loopback-status")
        yield Label("L=loopback  Esc=close  (slight delay is normal)", id="mic-test-hint")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        try:
            if self.app._transmitting:  # type: ignore[attr-defined]
                self.app.stop_ptt()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            loop = asyncio.get_running_loop()
            engine = self.app._audio_engine  # type: ignore[attr-defined]
            engine.set_energy_callback(self._on_energy)
            engine.set_spectrum_callback(self._on_spectrum)
            engine.start_vad(loop, threshold=0.0, callback=self._noop_vad)
        except Exception:
            pass
        self._refresh_ns_label()
        self._refresh_loopback_label()
        self._render_all()
        self.set_interval(0.05, self._poll)

    def on_unmount(self) -> None:
        try:
            engine = self.app._audio_engine  # type: ignore[attr-defined]
            engine.set_spectrum_callback(None)
            engine.stop_vad()
        except Exception:
            pass

    # ── Audio callbacks ───────────────────────────────────────────────────────

    def _noop_vad(self, is_voice: bool) -> None:
        pass

    def _on_energy(self, rms: float) -> None:
        self._latest_rms = rms
        self._new_data = True

    def _on_spectrum(self, pcm_bytes: bytes) -> None:
        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        mag = np.abs(np.fft.rfft(samples))
        # Use only the lower half of FFT bins (voice range) and bucket into rows
        half = len(mag) // 2 or 1
        mag = mag[:half]
        bucket_size = max(1, len(mag) // _SPEC_ROWS)

        # Compute per-bucket means first, then normalize by max bucket mean
        bucket_means: list[float] = []
        for row in range(_SPEC_ROWS - 1, -1, -1):
            start = row * bucket_size
            end = min(start + bucket_size, len(mag))
            bucket_means.append(float(mag[start:end].mean()) if start < len(mag) else 0.0)

        peak = max(bucket_means) if max(bucket_means) > 0 else 1.0

        column: list[str] = []
        for bm in bucket_means:
            ratio = bm / peak
            idx = min(int(ratio * (len(_INTENSITY) - 1)), len(_INTENSITY) - 1)
            column.append(_INTENSITY[idx])

        self._spec_history.append(column)
        self._new_data = True

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _poll(self) -> None:
        if self._new_data:
            self._new_data = False
            self._render_all()

    def _render_all(self) -> None:
        try:
            self.query_one("#spectrogram", Static).update(self._render_spectrogram())
            self.query_one("#level-bar", Static).update(self._render_level_bar(self._latest_rms))
        except Exception:
            pass

    def _render_spectrogram(self) -> str:
        cols = list(self._spec_history)
        rows: list[str] = []
        for row_idx in range(_SPEC_ROWS):
            line = "".join(col[row_idx] if col else " " for col in cols)
            rows.append(line)
        return "\n".join(rows)

    def _render_level_bar(self, rms: float) -> str:
        pct = min(100, int(rms / _RMS_MAX * 100))
        filled = _BAR_WIDTH * pct // 100
        bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
        return f"[green]{bar}[/green] {pct:3d}%"

    def _refresh_ns_label(self) -> None:
        try:
            engine = self.app._audio_engine  # type: ignore[attr-defined]
            ns_on = getattr(engine, "noise_suppression_enabled", False)
            label = "Noise Suppression: On" if ns_on else "Noise Suppression: Off"
            self.query_one("#ns-status", Label).update(label)
        except Exception:
            pass

    def _refresh_loopback_label(self) -> None:
        try:
            self.query_one("#loopback-status", Label).update(
                "Loopback: Off (audio is WebRTC)"
            )
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_toggle_loopback(self) -> None:
        # Loopback is not supported in the WebRTC audio pipeline.
        try:
            self.query_one("#loopback-status", Label).update(
                "Loopback: Off (audio is WebRTC)"
            )
        except Exception:
            pass
