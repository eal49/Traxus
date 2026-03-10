from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header

from client.widgets.channel_sidebar import ChannelSidebar
from client.widgets.input_bar import InputBar
from client.widgets.message_view import MessageView
from client.widgets.status_bar import StatusBar
from textual.containers import Horizontal, Vertical


class ChatScreen(Screen):
    """Main 3-panel chat layout."""

    DEFAULT_CSS = ""
    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield ChannelSidebar(id="sidebar")
            with Vertical(id="main-panel"):
                yield MessageView(id="messages", wrap=True, markup=True)
                yield InputBar(id="input-area")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#input-area", InputBar).focus_input()
        # Re-request channel list — the initial one from auth may have arrived
        # before this screen was mounted and would have been silently dropped.
        from shared.message_types import C2S
        self.app._send({"type": C2S.LIST_CHANNELS})  # type: ignore[attr-defined]

    # ── Event delegation from widgets ────────────────────────────────────────

    def on_channel_sidebar_channel_selected(
        self, event: ChannelSidebar.ChannelSelected
    ) -> None:
        self.app.join_channel(event.channel_name)  # type: ignore[attr-defined]

    def on_input_bar_message_submitted(
        self, event: InputBar.MessageSubmitted
    ) -> None:
        self.app.handle_input(event.text)  # type: ignore[attr-defined]

    # ── Update helpers (called from TraxusApp) ────────────────────────────────

    def _mv(self) -> MessageView | None:
        """Return the MessageView, or None if the screen is not yet/still mounted."""
        try:
            return self.query_one("#messages", MessageView)
        except Exception:
            return None

    def append_chat(self, payload: dict) -> None:
        mv = self._mv()
        if mv:
            mv.add_chat(payload)

    def append_system(self, content: str) -> None:
        mv = self._mv()
        if mv:
            mv.add_system(content)

    def append_error(self, content: str) -> None:
        mv = self._mv()
        if mv:
            mv.add_error(content)

    def append_local(self, content: str) -> None:
        mv = self._mv()
        if mv:
            mv.add_local(content)

    def update_channel_list(self, channels: list[dict]) -> None:
        sidebar = self.query_one("#sidebar", ChannelSidebar)
        sidebar.refresh_channels(channels)

    def set_active_channel(self, channel: str) -> None:
        sidebar = self.query_one("#sidebar", ChannelSidebar)
        sidebar.set_active(channel)
        input_bar = self.query_one("#input-area", InputBar)
        input_bar.set_channel(channel)

    def update_status(self, state: str, latency: int = 0, nick: str = "") -> None:
        self.query_one("#status-bar", StatusBar).set_state(state, latency, nick)

    def update_ptt(self, active: bool) -> None:
        self.query_one("#status-bar", StatusBar).update_ptt(active)

    def update_voice_state(self, users: list[dict]) -> None:
        if users:
            names = ", ".join(u.get("username", "?") for u in users)
            self.append_system(f"Voice members: {names}")
        else:
            self.append_system("Voice channel: no members")

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 4:
            self.app.toggle_ptt()  # type: ignore[attr-defined]
            event.stop()

    def action_ptt_toggle(self) -> None:
        self.app.toggle_ptt()  # type: ignore[attr-defined]

    def load_history(self, history: list[dict]) -> None:
        mv = self.query_one("#messages", MessageView)
        mv.clear()
        for msg in history:
            mv.add_chat(msg)
