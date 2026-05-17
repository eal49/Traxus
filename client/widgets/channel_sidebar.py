from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static


class ChannelSidebar(Widget):
    """Left panel showing all available channels."""

    DEFAULT_CSS = ""

    active_channel: reactive[str] = reactive("")

    class ChannelSelected(Message):
        def __init__(self, channel_name: str) -> None:
            super().__init__()
            self.channel_name = channel_name

    def compose(self) -> ComposeResult:
        yield Static("  CHANNELS", classes="sidebar-header")
        yield ListView(id="channel-list")

    def refresh_channels(self, channels: list[dict]) -> None:
        lv = self.query_one("#channel-list", ListView)
        lv.clear()
        text_channels = [ch for ch in channels if ch.get("type", "text") == "text"]
        voice_channels = [ch for ch in channels if ch.get("type", "text") == "voice"]

        if text_channels:
            header = ListItem(Label("  [dim bold]TEXT[/dim bold]", markup=True))
            header.can_focus = False
            lv.append(header)
        for ch in text_channels:
            name = ch["name"]
            item = ListItem(Label(f"  # {name}", markup=True), name=name)
            lv.append(item)

        if voice_channels:
            header = ListItem(Label("  [dim bold]VOICE[/dim bold]", markup=True))
            header.can_focus = False
            lv.append(header)
        for ch in voice_channels:
            name = ch["name"]
            item = ListItem(Label(f"  ♪ {name}", markup=True), name=name)
            lv.append(item)
            for member in ch.get("voice_members", []):
                nested = ListItem(Label(f"    · {member}", markup=True))
                nested.can_focus = False
                lv.append(nested)

        # Re-apply active highlight after refresh
        if self.active_channel:
            self._highlight(self.active_channel)

    def set_active(self, channel_name: str) -> None:
        self.active_channel = channel_name
        self._highlight(channel_name)

    def _highlight(self, channel_name: str) -> None:
        lv = self.query_one("#channel-list", ListView)
        for item in lv.query(ListItem):
            if item.name == channel_name:
                item.add_class("--highlight")
            else:
                item.remove_class("--highlight")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self.post_message(self.ChannelSelected(event.item.name))
