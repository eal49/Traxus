"""
ColorPickerScreen — 32×16 HSV color grid modal.

Rows 0–13: HSV colors (32 hues × 14 brightness/saturation bands).
Rows 14–15: grayscale ramp.

Navigate with arrow keys, Enter to confirm, Escape to cancel.
"""
from __future__ import annotations

import colorsys

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, Static

_COLS = 32
_HSV_ROWS = 14
_GRAY_ROWS = 2
_ROWS = _HSV_ROWS + _GRAY_ROWS  # 16


def _make_palette() -> list[list[str]]:
    """Return a 16×32 grid of hex color strings."""
    grid: list[list[str]] = []
    for row in range(_HSV_ROWS):
        band: list[str] = []
        # Vary saturation and value across rows for a nice spread
        t = row / (_HSV_ROWS - 1)
        if row < 7:
            s = 1.0
            v = 0.4 + 0.6 * (row / 6)
        else:
            s = 1.0 - 0.7 * ((row - 7) / 6)
            v = 1.0
        for col in range(_COLS):
            h = col / _COLS
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            band.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
        grid.append(band)
    for row in range(_GRAY_ROWS):
        band = []
        for col in range(_COLS):
            t = col / (_COLS - 1)
            if row == 0:
                # dark grays
                v = int(t * 127)
            else:
                # light grays
                v = 128 + int(t * 127)
            band.append(f"#{v:02x}{v:02x}{v:02x}")
        grid.append(band)
    return grid


_PALETTE = _make_palette()


class ColorPickerScreen(ModalScreen[str | None]):
    """32×16 HSV color picker. Dismisses with selected hex or None."""

    DEFAULT_CSS = """
    ColorPickerScreen {
        align: center middle;
    }
    #picker-container {
        width: 68;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #picker-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #picker-grid {
        height: 16;
    }
    #picker-indicator {
        height: 1;
    }
    #picker-preview {
        height: 2;
        margin-top: 1;
    }
    #picker-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = []

    def __init__(self, current_hex: str = "") -> None:
        super().__init__()
        self._col = 0
        self._row = 0
        # Try to pre-select the cell closest to the current color
        if current_hex:
            self._col, self._row = self._find_closest(current_hex)

    def compose(self) -> ComposeResult:
        with Static(id="picker-container"):
            yield Label("Nick Color Picker", id="picker-title")
            yield Static(id="picker-grid")
            yield Static(id="picker-indicator")
            yield Static(id="picker-preview")
            yield Label("↑↓←→ navigate   Enter accept   Esc cancel", id="picker-hint")

    def on_mount(self) -> None:
        self._refresh_display()

    def _selected_hex(self) -> str:
        return _PALETTE[self._row][self._col]

    def _build_grid(self) -> str:
        lines: list[str] = []
        for r, row in enumerate(_PALETTE):
            parts: list[str] = []
            for c, hex_color in enumerate(row):
                if r == self._row and c == self._col:
                    parts.append(f"[on {hex_color}]◆◆[/]")
                else:
                    parts.append(f"[on {hex_color}]  [/]")
            lines.append("".join(parts))
        return "\n".join(lines)

    def _build_indicator(self) -> str:
        pos = self._col * 2
        return " " * pos + "▼"

    def _build_preview(self) -> str:
        hex_color = self._selected_hex()
        try:
            nick = self.app.username  # type: ignore[attr-defined]
        except Exception:
            nick = "You"
        return f"[bold {hex_color}]{nick}[/bold {hex_color}]\n{hex_color}"

    def _refresh_display(self) -> None:
        self.query_one("#picker-grid", Static).update(self._build_grid())
        self.query_one("#picker-indicator", Static).update(self._build_indicator())
        self.query_one("#picker-preview", Static).update(self._build_preview())

    def on_key(self, event) -> None:
        key = event.key
        if key == "left":
            self._col = max(0, self._col - 1)
        elif key == "right":
            self._col = min(_COLS - 1, self._col + 1)
        elif key == "up":
            self._row = max(0, self._row - 1)
        elif key == "down":
            self._row = min(_ROWS - 1, self._row + 1)
        elif key == "enter":
            self.dismiss(self._selected_hex())
            return
        elif key == "escape":
            self.dismiss(None)
            return
        else:
            return
        event.stop()
        self._refresh_display()

    def _find_closest(self, hex_color: str) -> tuple[int, int]:
        """Return (col, row) of the palette cell closest to hex_color."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
        except (ValueError, IndexError):
            return 0, 0
        best_dist = float("inf")
        best_col, best_row = 0, 0
        for row_idx, row in enumerate(_PALETTE):
            for col_idx, cell in enumerate(row):
                try:
                    cr = int(cell[1:3], 16)
                    cg = int(cell[3:5], 16)
                    cb = int(cell[5:7], 16)
                except (ValueError, IndexError):
                    continue
                dist = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_col, best_row = col_idx, row_idx
        return best_col, best_row
