from __future__ import annotations

import hashlib
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


def nick_color(username: str) -> str:
    idx = int(hashlib.md5(username.encode()).hexdigest(), 16) % len(_NICK_PALETTE)
    return _NICK_PALETTE[idx]


class MessageView(RichLog):
    """
    Scrollable message log. Renders chat messages with Rich markup:
      [dim]HH:MM[/dim]  [bold cyan]nick[/bold cyan]  content

    Stores all formatted lines so they can be re-rendered at the correct wrap
    width whenever the widget is resized.
    """

    DEFAULT_CSS = ""

    def on_mount(self) -> None:
        self.auto_scroll = True
        self.markup = True
        self.highlight = False
        self.wrap = True
        self.min_width = 1
        self._lines: list[str] = []
        self._last_width: int = 0

    def _emit(self, markup: str) -> None:
        self._lines.append(markup)
        self.write(markup)

    def on_resize(self) -> None:
        width = self.scrollable_content_region.width
        if width == self._last_width:
            return
        self._last_width = width
        lines = list(self._lines)
        self.clear()
        self._lines = lines
        for line in lines:
            self.write(line)

    def add_chat(self, payload: dict, self_username: str = "") -> None:
        ts = _fmt_ts(payload.get("ts"))
        raw_nick = str(payload.get("username", "?"))
        nick = _escape(raw_nick)
        content = _escape(str(payload.get("content", "")))
        if self_username and raw_nick == self_username:
            nick_markup = f"[bold white]{nick}[/bold white]"
        else:
            color = nick_color(raw_nick)
            nick_markup = f"[bold {color}]{nick}[/bold {color}]"
        self._emit(f"[dim]{ts}[/dim]  {nick_markup}  {content}")

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
