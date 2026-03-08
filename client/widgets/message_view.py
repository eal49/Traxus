from __future__ import annotations

from datetime import datetime

from textual.widgets import RichLog


class MessageView(RichLog):
    """
    Scrollable message log. Renders chat messages with Rich markup:
      [dim]HH:MM[/dim]  [bold cyan]nick[/bold cyan]  content
    """

    DEFAULT_CSS = ""

    def on_mount(self) -> None:
        self.auto_scroll = True
        self.markup = True
        self.highlight = False

    def add_chat(self, payload: dict) -> None:
        ts = _fmt_ts(payload.get("ts"))
        nick = _escape(str(payload.get("username", "?")))
        content = _escape(str(payload.get("content", "")))
        self.write(
            f"[dim]{ts}[/dim]  [bold #57f287]{nick}[/bold #57f287]  {content}"
        )

    def add_system(self, content: str) -> None:
        self.write(f"[dim italic #72767d]  {_escape(content)}[/dim italic #72767d]")

    def add_error(self, content: str) -> None:
        self.write(f"[bold #ed4245]  ✗ {_escape(content)}[/bold #ed4245]")

    def add_local(self, content: str) -> None:
        """Display a message that originates locally (e.g., /help output)."""
        self.write(f"[#5865f2]{_escape(content)}[/#5865f2]")

    def add_separator(self, label: str = "") -> None:
        self.write(f"[dim]{'─' * 20}  {label}[/dim]" if label else "[dim]" + "─" * 40 + "[/dim]")


def _fmt_ts(ts: float | None) -> str:
    if ts is None:
        return "--:--"
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _escape(text: str) -> str:
    """Escape Rich markup special chars in user content."""
    return text.replace("[", r"\[").replace("]", r"\]")
