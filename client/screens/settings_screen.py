"""
Settings modal screens for Traxus.

SettingsScreen: top-level navigable menu of setting categories.
PttKeyScreen:   key-capture screen for rebinding the PTT key.
"""
from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


class SettingsScreen(ModalScreen[str | None]):
    """Top-level settings menu.  Dismisses with the new PTT key string, or
    None if the user pressed Escape without making a change."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Label("Settings", id="settings-title")
        yield ListView(
            ListItem(Label("PTT Key"), id="item-ptt-key"),
            id="settings-list",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "item-ptt-key":
            current_key: str = getattr(self.app, "_ptt_key", "f9")
            self.app.push_screen(PttKeyScreen(current_key), self._on_ptt_key)

    def _on_ptt_key(self, new_key: str | None) -> None:
        """Callback from PttKeyScreen.  Forward the chosen key to the app."""
        if new_key is not None:
            self.dismiss(new_key)
        # else: user cancelled — stay on SettingsScreen


class PttKeyScreen(ModalScreen[str | None]):
    """Key-capture screen.  Shows the current PTT binding and waits for a
    keypress or mouse button click.

    Dismisses with the captured binding string (key name or "mouseN"), or
    None if Escape was pressed.
    """

    def __init__(self, current_key: str) -> None:
        super().__init__()
        self._current_key = current_key

    def compose(self) -> ComposeResult:
        yield Label(f"Current PTT key: {self._current_key}", id="ptt-current")
        yield Label(
            "Press any key or click a mouse button — Escape to cancel",
            id="ptt-prompt",
        )
        yield Label(
            "Note: only left-click (1) and middle-click (2) work reliably in most terminals.",
            id="ptt-note",
        )

    def on_key(self, event: events.Key) -> None:
        event.stop()
        if event.key == "escape":
            self.dismiss(None)
        else:
            self.dismiss(event.key)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        self.dismiss(f"mouse{event.button}")
