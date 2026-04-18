"""
VadSensitivityScreen — live spectrogram + threshold adjuster for VAD.

Shows a rolling ASCII spectrogram (frequency × time) and an RMS level bar
with a ▲ threshold marker. ←/→ adjust coarsely, ↑/↓ finely.

Dismisses with the chosen threshold float on Enter, or None on Escape.
"""
from __future__ import annotations

import asyncio
from collections import deque

import numpy as np

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static

_COARSE_STEP: float = 50.0
_FINE_STEP: float   = 10.0
_MIN_THRESHOLD: float = 1.0
_RMS_MAX: float     = 1500.0
_SPEC_COLS: int     = 48
_SPEC_ROWS: int     = 16
_BAR_WIDTH: int     = 40
_INTENSITY: str     = " ░▒▓█"


class VadSensitivityScreen(ModalScreen[float | None]):
    """Live mic spectrogram + adjustable VAD threshold.

    Dismisses with the chosen threshold float on Enter, None on Escape.
    """

    DEFAULT_CSS = """
    VadSensitivityScreen {
        align: center middle;
    }
    #vad-sens-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #vad-spectrogram {
        width: 52;
        height: 18;
        border: round $accent;
        background: $surface;
        padding: 0 1;
    }
    #vad-level-bar {
        width: 52;
        height: 1;
        margin-top: 1;
    }
    #vad-status {
        width: 52;
        text-align: center;
        margin-top: 0;
    }
    #vad-threshold-label {
        width: 52;
        text-align: center;
        margin-top: 1;
    }
    #vad-hint {
        width: 52;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = []

    def __init__(self, initial_threshold: float = 250.0) -> None:
        super().__init__()
        self._threshold: float = max(_MIN_THRESHOLD, min(_RMS_MAX, initial_threshold))
        self._spec_history: deque[list[str]] = deque(
            [[" "] * _SPEC_ROWS for _ in range(_SPEC_COLS)], maxlen=_SPEC_COLS
        )
        self._latest_rms: float = 0.0
        self._new_data: bool = False
        self._dismissing: bool = False

    # ── Compose ───────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label("VAD Sensitivity", id="vad-sens-title")
        yield Static("", id="vad-spectrogram")
        yield Static("", id="vad-level-bar")
        yield Static("", id="vad-status")
        yield Static("", id="vad-threshold-label")
        yield Label("←/→ coarse   ↑/↓ fine   Enter=save   Esc=cancel", id="vad-hint")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        try:
            if self.app._audio_engine.transmitting:  # type: ignore[attr-defined]
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
        half = len(mag) // 2 or 1
        mag = mag[:half]
        bucket_size = max(1, len(mag) // _SPEC_ROWS)

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

    # ── Poll ──────────────────────────────────────────────────────────────────

    def _poll(self) -> None:
        if self._new_data:
            self._new_data = False
            self._render_all()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_spectrogram(self) -> str:
        cols = list(self._spec_history)
        rows: list[str] = []
        for row_idx in range(_SPEC_ROWS):
            line = "".join(col[row_idx] if col else " " for col in cols)
            rows.append(line)
        return "\n".join(rows)

    def _render_level_bar(self, rms: float, threshold: float) -> str:
        pct = min(100, int(rms / _RMS_MAX * 100))
        filled = _BAR_WIDTH * pct // 100
        bar_chars = list("░" * _BAR_WIDTH)
        for i in range(filled):
            bar_chars[i] = "█"
        marker_col = min(_BAR_WIDTH - 1, int(threshold / _RMS_MAX * _BAR_WIDTH))
        bar_chars[marker_col] = "▲"
        bar = "".join(bar_chars)
        return f"[green]{bar}[/green] {pct:3d}%"

    def _render_status(self, rms: float, threshold: float) -> str:
        if rms >= threshold:
            return "[green]● Voice detected[/green]"
        return "[dim]○ Silence[/dim]"

    def _render_threshold_label(self) -> str:
        return f"Threshold: {int(self._threshold)}"

    def _render_all(self) -> None:
        if self._dismissing:
            return
        try:
            self.query_one("#vad-spectrogram", Static).update(self._render_spectrogram())
            self.query_one("#vad-level-bar", Static).update(
                self._render_level_bar(self._latest_rms, self._threshold)
            )
            self.query_one("#vad-status", Static).update(
                self._render_status(self._latest_rms, self._threshold)
            )
            self.query_one("#vad-threshold-label", Static).update(
                self._render_threshold_label()
            )
        except Exception:
            pass

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def on_key(self, event) -> None:
        key = event.key
        if key == "right":
            self._threshold = min(_RMS_MAX, self._threshold + _COARSE_STEP)
        elif key == "left":
            self._threshold = max(_MIN_THRESHOLD, self._threshold - _COARSE_STEP)
        elif key == "up":
            self._threshold = min(_RMS_MAX, self._threshold + _FINE_STEP)
        elif key == "down":
            self._threshold = max(_MIN_THRESHOLD, self._threshold - _FINE_STEP)
        elif key == "enter":
            self._dismissing = True
            self.dismiss(self._threshold)
            return
        elif key == "escape":
            self._dismissing = True
            self.dismiss(None)
            return
        else:
            return
        event.stop()
        self._render_all()
