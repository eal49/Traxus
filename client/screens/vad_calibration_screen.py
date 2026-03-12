"""
VadCalibrationScreen — live microphone energy visualiser for custom VAD threshold.

Shows a rolling ASCII bar chart of incoming RMS energy.  The user moves a
threshold line with Up/Down (fine) or PageUp/PageDown (coarse), then presses
Enter to save or Escape to cancel.
"""
from __future__ import annotations

import asyncio
from collections import deque

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static

_MAX_DISPLAY: float = 1500.0  # top of the chart
_CHART_ROWS: int = 24         # number of visible energy rows
_CHART_WIDTH: int = 40        # horizontal width in chars
_HISTORY: int = _CHART_WIDTH  # one column per sample
_FINE_STEP: float = 10.0
_COARSE_STEP: float = 100.0
_MIN_THRESHOLD: float = 1.0
_MAX_THRESHOLD: float = _MAX_DISPLAY


class VadCalibrationScreen(ModalScreen[float | None]):
    """Live mic energy display with adjustable VAD threshold bar.

    Dismisses with the chosen threshold float, or None if the user cancelled.
    """

    DEFAULT_CSS = """
    VadCalibrationScreen {
        align: center middle;
    }
    #calibration-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #energy-chart {
        width: 50;
        height: 26;
        border: round $accent;
        background: $surface;
        padding: 0 1;
    }
    #calibration-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("up",       "adjust_up",        "Raise threshold"),
        ("down",     "adjust_down",      "Lower threshold"),
        ("pageup",   "adjust_page_up",   "Raise threshold (large)"),
        ("pagedown", "adjust_page_down", "Lower threshold (large)"),
        ("enter",    "confirm",          "Save"),
        ("escape",   "cancel",           "Cancel"),
    ]

    def __init__(self, initial_threshold: float) -> None:
        super().__init__()
        self._threshold: float = max(_MIN_THRESHOLD, min(_MAX_THRESHOLD, initial_threshold))
        self._energy_history: deque[float] = deque([0.0] * _HISTORY, maxlen=_HISTORY)
        self._new_sample: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label("VAD Calibration", id="calibration-title")
        yield Static("", id="energy-chart")
        yield Label(
            "↑/↓ fine  PgUp/PgDn coarse  Enter=save  Esc=cancel",
            id="calibration-hint",
        )

    def on_mount(self) -> None:
        # Stop any active PTT so the red indicator doesn't stay on while the
        # VAD callback is replaced by the dummy below.
        try:
            if self.app._audio_engine.transmitting:  # type: ignore[attr-defined]
                self.app.stop_ptt()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            loop = asyncio.get_running_loop()
            engine = self.app._audio_engine  # type: ignore[attr-defined]
            engine.set_energy_callback(self._on_raw_energy)
            engine.start_vad(loop, threshold=0.0, callback=self._dummy_vad_callback)
        except Exception:
            pass
        self._refresh_chart()
        self.set_interval(0.05, self._poll_chart)

    def on_unmount(self) -> None:
        try:
            engine = self.app._audio_engine  # type: ignore[attr-defined]
            engine.stop_vad()
        except Exception:
            pass

    # ── Audio callbacks (called from asyncio loop via call_soon_threadsafe) ───

    def _dummy_vad_callback(self, is_voice: bool) -> None:
        """VAD transitions are not used in calibration mode."""

    def _on_raw_energy(self, rms: float) -> None:
        self._energy_history.append(rms)
        self._new_sample = True

    # ── Chart rendering ────────────────────────────────────────────────────────

    def _poll_chart(self) -> None:
        if self._new_sample:
            self._new_sample = False
            self._refresh_chart()

    def _refresh_chart(self) -> None:
        history = list(self._energy_history)
        latest_rms = history[-1] if history else 0.0
        lines: list[str] = []

        for row_idx in range(_CHART_ROWS):
            # row 0 = top (MAX_DISPLAY), row _CHART_ROWS-1 = bottom (0)
            band_top = _MAX_DISPLAY - row_idx * (_MAX_DISPLAY / _CHART_ROWS)
            band_bot = _MAX_DISPLAY - (row_idx + 1) * (_MAX_DISPLAY / _CHART_ROWS)
            band_mid = (band_top + band_bot) / 2.0

            bar_char = "█" if latest_rms >= band_mid else " "
            bar = bar_char * _CHART_WIDTH

            if band_bot <= self._threshold <= band_top:
                line = f"{bar} [yellow]◀ {self._threshold:.0f}[/yellow]"
            else:
                line = bar

            lines.append(line)

        chart_text = "\n".join(lines)
        try:
            self.query_one("#energy-chart", Static).update(chart_text)
        except Exception:
            pass

    # ── Key actions ────────────────────────────────────────────────────────────

    def action_adjust_up(self) -> None:
        self._threshold = min(_MAX_THRESHOLD, self._threshold + _FINE_STEP)
        self._refresh_chart()

    def action_adjust_down(self) -> None:
        self._threshold = max(_MIN_THRESHOLD, self._threshold - _FINE_STEP)
        self._refresh_chart()

    def action_adjust_page_up(self) -> None:
        self._threshold = min(_MAX_THRESHOLD, self._threshold + _COARSE_STEP)
        self._refresh_chart()

    def action_adjust_page_down(self) -> None:
        self._threshold = max(_MIN_THRESHOLD, self._threshold - _COARSE_STEP)
        self._refresh_chart()

    def action_confirm(self) -> None:
        self.dismiss(self._threshold)

    def action_cancel(self) -> None:
        self.dismiss(None)
