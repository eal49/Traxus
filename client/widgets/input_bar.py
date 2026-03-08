from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static


class InputBar(Widget):
    """Bottom bar: channel label + text input."""

    DEFAULT_CSS = ""

    current_channel: reactive[str] = reactive("general")

    class MessageSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def compose(self) -> ComposeResult:
        yield Static("#general ›", classes="chan-label", id="chan-label")
        yield Input(
            placeholder="Type a message or /help …",
            id="message-input",
        )

    def watch_current_channel(self, channel: str) -> None:
        try:
            self.query_one("#chan-label", Static).update(f"#{channel} ›")
        except Exception:
            pass

    def set_channel(self, channel: str) -> None:
        self.current_channel = channel

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self.post_message(self.MessageSubmitted(text))
            event.input.clear()

    def focus_input(self) -> None:
        self.query_one("#message-input", Input).focus()
