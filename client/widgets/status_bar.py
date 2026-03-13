from __future__ import annotations

from textual.widgets import Static


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


class StatusBar(Static):
    """Bottom status strip showing connection state, latency, and nick."""

    DEFAULT_CSS = ""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._state = "disconnected"
        self._latency = 0
        self._nick = ""
        self._ptt_active = False
        self._vad_listening = False
        self._voice_channel = ""

    def _build_markup(self) -> str:
        color = _STATE_COLORS.get(self._state, "#dcddde")
        icon  = _STATE_ICONS.get(self._state, "?")
        lat   = f"  {self._latency}ms" if self._state == "connected" else ""
        markup = f"[{color}]{icon} {self._state.upper()}[/{color}]{lat}"
        if self._nick:
            markup += f"   [bold]{self._nick}[/bold]"
        if self._voice_channel:
            markup += f"   [bold #57f287]🔊 {self._voice_channel}[/bold #57f287]"
        if self._ptt_active:
            markup += r"   [bold white]🎤 PTT ON[/bold white]"
        elif self._vad_listening:
            markup += r"   [bold yellow]🎤 LISTENING[/bold yellow]"
        return markup

    def _refresh_content(self) -> None:
        """Push new markup to Static.update() — guaranteed to repaint."""
        self.update(self._build_markup())

    def set_state(
        self,
        state: str,
        latency: int = 0,
        nick: str = "",
    ) -> None:
        self._state = state
        if latency:
            self._latency = latency
        if nick:
            self._nick = nick
        self._refresh_content()

    def update_ptt(self, active: bool) -> None:
        self._ptt_active = active
        self.set_class(active, "ptt-active")
        self._refresh_content()

    def update_vad_listening(self, active: bool) -> None:
        self._vad_listening = active
        self._refresh_content()

    def update_voice_channel(self, name: str) -> None:
        self._voice_channel = name
        self._refresh_content()
