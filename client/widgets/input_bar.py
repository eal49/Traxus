from __future__ import annotations

import re

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from client.commands import KNOWN_COMMANDS
from client.settings import MAX_HISTORY, load_history, save_history

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

    def on_mount(self) -> None:
        self._history: list[str] = load_history()
        self._history_pos: int | None = None
        self._draft: str = ""
        self._completions: list[str] = []
        self._completion_pos: int | None = None
        self._completion_prefix: str = ""
        self._completing: bool = False

    def watch_current_channel(self, channel: str) -> None:
        try:
            self.query_one("#chan-label", Static).update(f"#{channel} ›")
        except Exception:
            pass

    def set_channel(self, channel: str) -> None:
        self.current_channel = channel

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            event.stop()
            self._history_up()
        elif event.key == "down":
            event.stop()
            self._history_down()
        elif event.key == "tab":
            event.stop()
            self._complete(forward=True)
        elif event.key == "shift+tab":
            event.stop()
            self._complete(forward=False)
        elif event.key == "escape":
            if self._completion_pos is not None:
                event.stop()
                inp = self._input()
                if inp is not None:
                    self._completing = True
                    inp.value = self._completion_prefix
                    inp.cursor_position = len(inp.value)
                    self._completing = False
                self._completion_pos = None
                self._completions = []
                self._completion_prefix = ""

    def _input(self) -> Input | None:
        try:
            return self.query_one("#message-input", Input)
        except Exception:
            return None

    def _history_up(self) -> None:
        if not self._history:
            return
        inp = self._input()
        if inp is None:
            return
        if self._history_pos is None:
            self._draft = inp.value
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        else:
            return  # already at oldest
        inp.value = self._history[self._history_pos]
        inp.cursor_position = len(inp.value)

    def _history_down(self) -> None:
        if self._history_pos is None:
            return
        inp = self._input()
        if inp is None:
            return
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            inp.value = self._history[self._history_pos]
        else:
            self._history_pos = None
            inp.value = self._draft
        inp.cursor_position = len(inp.value)

    def _complete(self, forward: bool) -> None:
        inp = self._input()
        if inp is None:
            return
        value = inp.value
        if not value.startswith("/") or len(value) < 2:
            return
        prefix = value[1:]
        if self._completion_pos is None:
            candidates = sorted(c for c in KNOWN_COMMANDS if c.startswith(prefix))
            if not candidates:
                return
            if len(candidates) == 1:
                self._completing = True
                inp.value = f"/{candidates[0]}"
                inp.cursor_position = len(inp.value)
                self._completing = False
                return
            self._completions = candidates
            self._completion_prefix = value
            self._completion_pos = 0 if forward else len(candidates) - 1
        else:
            step = 1 if forward else -1
            self._completion_pos = (self._completion_pos + step) % len(self._completions)
        self._completing = True
        inp.value = f"/{self._completions[self._completion_pos]}"
        inp.cursor_position = len(inp.value)
        self._completing = False

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self._completing:
            self._completion_pos = None
            self._completions = []
        m = _SELECTION_CMD_RE.match(event.value)
        if m:
            command = m.group(1)
            event.input.value = ""
            self.post_message(self.SelectionModeRequested(command))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            if text.startswith("/"):
                if not self._history or self._history[-1] != text:
                    self._history.append(text)
                    if len(self._history) > MAX_HISTORY:
                        self._history = self._history[-MAX_HISTORY:]
                    save_history(self._history)
            self._history_pos = None
            self._draft = ""
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
