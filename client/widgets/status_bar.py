from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


_STATE_COLORS = {
    "connected":    "#57f287",   # green
    "connecting":   "#fee75c",   # yellow
    "reconnecting": "#fee75c",
    "disconnected": "#ed4245",   # red
}

_STATE_ICONS = {
    "connected":    "●",
    "connecting":   "◌",
    "reconnecting": "◌",
    "disconnected": "○",
}


class StatusBar(Widget):
    """Bottom status strip showing connection state, latency, and nick."""

    DEFAULT_CSS = ""

    state:      reactive[str]  = reactive("disconnected")
    latency:    reactive[int]  = reactive(0)
    nick:       reactive[str]  = reactive("")
    ptt_active: reactive[bool] = reactive(False)

    def render(self) -> Text:
        color = _STATE_COLORS.get(self.state, "#dcddde")
        icon  = _STATE_ICONS.get(self.state, "?")
        lat   = f"  {self.latency}ms" if self.state == "connected" else ""
        markup = f"[{color}]{icon} {self.state.upper()}[/{color}]{lat}"
        if self.nick:
            markup += f"   [bold]{self.nick}[/bold]"
        if self.ptt_active:
            markup += r"   [bold white]🎤 PTT ON[/bold white]"
        return Text.from_markup(markup)

    # watch_* fires through Textual's DOM pipeline — guaranteed to repaint.
    def watch_ptt_active(self, active: bool) -> None:
        self.set_class(active, "ptt-active")
        self.refresh()

    def set_state(
        self,
        state: str,
        latency: int = 0,
        nick: str = "",
    ) -> None:
        self.state = state
        if latency:
            self.latency = latency
        if nick:
            self.nick = nick

    def update_ptt(self, active: bool) -> None:
        self.ptt_active = active
