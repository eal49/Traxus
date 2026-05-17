from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Static

from client.widgets.channel_sidebar import ChannelSidebar
from client.widgets.input_bar import InputBar
from client.widgets.member_panel import MemberPanel
from client.widgets.message_view import MessageView
from client.widgets.status_bar import StatusBar
from textual.containers import Horizontal, Vertical


class ChatScreen(Screen):
    """Main 3-panel chat layout."""

    DEFAULT_CSS = """
    #pin-header {
        background: $boost;
        color: $text;
        padding: 0 1;
        height: 1;
        display: none;
    }
    """
    BINDINGS = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            yield ChannelSidebar(id="sidebar")
            with Vertical(id="main-panel"):
                yield Static("", id="pin-header")
                yield MessageView(id="messages", wrap=True, markup=True)
                yield InputBar(id="input-area")
            yield MemberPanel(id="members")
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#input-area", InputBar).focus_input()
        # Sync status bar with current app state — the "connected" message
        # arrives before ChatScreen exists, so the StatusBar never saw it.
        self.update_status(
            self.app.connection_state,  # type: ignore[attr-defined]
            nick=self.app.username,     # type: ignore[attr-defined]
        )
        # Re-request channel list — the initial one from auth may have arrived
        # before this screen was mounted and would have been silently dropped.
        from shared.message_types import C2S
        self.app._send({"type": C2S.LIST_CHANNELS})  # type: ignore[attr-defined]
        # Populate member panel from cached data — the user_list message may
        # have arrived before the screen widgets were fully mounted, causing
        # update_members() to silently fail inside the try/except.
        current = self.app.current_channel  # type: ignore[attr-defined]
        members = self.app._channel_members.get(current, [])  # type: ignore[attr-defined]
        self.update_members(members)
        # Sync must_change_password nudge — the reactive watcher fires before
        # ChatScreen is mounted so the StatusBar never receives the initial call.
        if self.app._must_change_password:  # type: ignore[attr-defined]
            self.query_one("#status-bar", StatusBar).update_must_change_password(True)

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
            mv.add_chat(payload, self_username=self.app.username,  # type: ignore[attr-defined]
                        self_color=getattr(self.app, "_nick_color", ""))

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
        try:
            sidebar = self.query_one("#sidebar", ChannelSidebar)
            sidebar.set_active(channel)
            input_bar = self.query_one("#input-area", InputBar)
            input_bar.set_channel(channel)
        except Exception:
            pass

    def update_status(self, state: str, latency: int = 0, nick: str = "") -> None:
        self.query_one("#status-bar", StatusBar).set_state(state, latency, nick)

    def update_ptt(self, active: bool) -> None:
        self.query_one("#status-bar", StatusBar).update_ptt(active)

    def update_vad_listening(self, active: bool) -> None:
        self.query_one("#status-bar", StatusBar).update_vad_listening(active)

    def update_voice_channel(self, name: str) -> None:
        try:
            self.query_one("#status-bar", StatusBar).update_voice_channel(name)
        except Exception:
            pass

    def update_members(self, members: list[dict]) -> None:
        try:
            self.query_one("#members", MemberPanel).set_members(members)
        except Exception:
            pass

    def update_member_voice(self, voice_users: list[dict]) -> None:
        try:
            self.query_one("#members", MemberPanel).update_voice(voice_users)
        except Exception:
            pass

    def update_voice_state(self, users: list[dict]) -> None:
        if users:
            names = ", ".join(u.get("username", "?") for u in users)
            self.append_system(f"Voice members: {names}")
        else:
            self.append_system("Voice channel: no members")

    def update_pin(self, pin: dict | None) -> None:
        try:
            header = self.query_one("#pin-header", Static)
            if pin:
                nick = pin.get("username", "?")
                content = pin.get("content", "")
                header.update(f"📌 @{nick}: {content}")
                header.display = True
            else:
                header.display = False
        except Exception:
            pass

    def action_ptt_toggle(self) -> None:
        self.app.toggle_ptt()  # type: ignore[attr-defined]

    def load_history(self, history: list[dict]) -> None:
        try:
            mv = self.query_one("#messages", MessageView)
        except Exception:
            return
        mv.clear()
        mv._lines = []
        mv._payloads = []
        username = self.app.username  # type: ignore[attr-defined]
        nick_color = getattr(self.app, "_nick_color", "")
        for msg in history:
            mv.add_chat(msg, self_username=username, self_color=nick_color)
