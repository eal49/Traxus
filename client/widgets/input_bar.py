from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

_SELECTION_CMD_RE = re.compile(r"^/(quote|pin)\s$")


class InputBar(Widget):
    """Bottom bar: channel label + text input."""

    DEFAULT_CSS = ""

    current_channel: reactive[str] = reactive("general")

    class MessageSubmitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class SelectionModeRequested(Message):
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

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

    def on_input_changed(self, event: Input.Changed) -> None:
        m = _SELECTION_CMD_RE.match(event.value)
        if m:
            command = m.group(1)
            event.input.value = ""
            self.post_message(self.SelectionModeRequested(command))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self.post_message(self.MessageSubmitted(text))
            event.input.clear()

    def focus_input(self) -> None:
        self.query_one("#message-input", Input).focus()

    def disable(self) -> None:
        try:
            inp = self.query_one("#message-input", Input)
            inp.disabled = True
        except Exception:
            pass

    def enable(self) -> None:
        try:
            inp = self.query_one("#message-input", Input)
            inp.disabled = False
            inp.focus()
        except Exception:
            pass
