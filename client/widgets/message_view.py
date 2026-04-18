from __future__ import annotations

import hashlib
import re as _re
from datetime import datetime

from textual.widgets import RichLog

_NICK_PALETTE = [
    "#5865f2",  # blurple
    "#57f287",  # green
    "#fee75c",  # yellow
    "#eb459e",  # pink
    "#ed4245",  # red
    "#00b0f4",  # cyan
    "#f47fff",  # magenta
    "#faa61a",  # orange
]

_MARKUP_RE = _re.compile(r"\[.*?\]")


def nick_color(username: str) -> str:
    idx = int(hashlib.md5(username.encode()).hexdigest(), 16) % len(_NICK_PALETTE)
    return _NICK_PALETTE[idx]


def _strip_markup(markup: str) -> str:
    return _MARKUP_RE.sub("", markup)


class MessageView(RichLog):
    """
    Scrollable message log. Renders chat messages with Rich markup:
      [dim]HH:MM[/dim]  [bold cyan]nick[/bold cyan]  content

    Stores all formatted lines so they can be re-rendered at the correct wrap
    width whenever the widget is resized.

    Also supports a keyboard cursor for line selection (used by /quote and /pin).
    """

    DEFAULT_CSS = ""

    def on_mount(self) -> None:
        self.auto_scroll = True
        self.markup = True
        self.highlight = False
        self.wrap = True
        self.min_width = 1
        self._lines: list[str] = []
        self._payloads: list[dict | None] = []
        self._cursor: int | None = None
        self._last_width: int = 0

    def _emit(self, markup: str, payload: dict | None = None) -> None:
        self._lines.append(markup)
        self._payloads.append(payload)
        if self._cursor is None:
            self.write(markup)

    def on_resize(self) -> None:
        width = self.scrollable_content_region.width
        if width == self._last_width:
            return
        self._last_width = width
        self._redraw()

    def _redraw(self) -> None:
        lines = list(self._lines)
        payloads = list(self._payloads)
        self.clear()
        self._lines = lines
        self._payloads = payloads
        for i, line in enumerate(lines):
            if self._cursor is not None and i == self._cursor:
                self.write(f"[reverse]{_strip_markup(line)}[/reverse]")
            else:
                self.write(line)

    # ── Selection mode ────────────────────────────────────────────────────────

    def enter_selection_mode(self) -> None:
        self._cursor = max(0, len(self._lines) - 1) if self._lines else 0
        self._redraw()

    def exit_selection_mode(self) -> None:
        self._cursor = None
        self._redraw()

    def move_cursor(self, delta: int) -> None:
        if self._cursor is None or not self._lines:
            return
        self._cursor = max(0, min(len(self._lines) - 1, self._cursor + delta))
        self._redraw()

    def selected_payload(self) -> dict | None:
        if self._cursor is None or not self._payloads:
            return None
        return self._payloads[self._cursor]

    def selected_line_markup(self) -> str:
        if self._cursor is None or not self._lines:
            return ""
        return self._lines[self._cursor]

    # ── Message helpers ───────────────────────────────────────────────────────

    _QUOTE_SEP = " › "

    def add_chat(self, payload: dict, self_username: str = "", self_color: str = "") -> None:
        ts = _fmt_ts(payload.get("ts"))
        raw_nick = str(payload.get("username", "?"))
        nick = _escape(raw_nick)
        raw_content = str(payload.get("content", ""))
        if self_username and raw_nick == self_username:
            color = self_color or "white"
            nick_markup = f"[bold {color}]{nick}[/bold {color}]"
        else:
            color = nick_color(raw_nick)
            nick_markup = f"[bold {color}]{nick}[/bold {color}]"

        if self._QUOTE_SEP in raw_content:
            q, _, reply = raw_content.partition(self._QUOTE_SEP)
            q_markup = f"[dim italic]╷ {_escape(q.lstrip('> '))}[/dim italic]"
            reply_markup = _escape(reply)
            content_markup = f"{q_markup}\n  {reply_markup}" if reply_markup.strip() else q_markup
        else:
            content_markup = _escape(raw_content)

        self._emit(f"[dim]{ts}[/dim]  {nick_markup}  {content_markup}", payload)

    def add_system(self, content: str) -> None:
        self._emit(f"[dim italic #72767d]  {_escape(content)}[/dim italic #72767d]")

    def add_error(self, content: str) -> None:
        self._emit(f"[bold #ed4245]  ✗ {_escape(content)}[/bold #ed4245]")

    def add_local(self, content: str) -> None:
        """Display a message that originates locally (e.g., /help output)."""
        self._emit(f"[#5865f2]{_escape(content)}[/#5865f2]")

    def add_separator(self, label: str = "") -> None:
        self._emit(f"[dim]{'─' * 20}  {label}[/dim]" if label else "[dim]" + "─" * 40 + "[/dim]")


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "--:--"
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _escape(text: str) -> str:
    """Escape Rich markup special chars in user content."""
    return text.replace("[", r"\[").replace("]", r"\]")
