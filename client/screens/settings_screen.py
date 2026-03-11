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
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        mode_label = "Toggle" if current_mode == "toggle" else "Hold"
        yield Label("Settings", id="settings-title")
        yield ListView(
            ListItem(Label("PTT Key"), id="item-ptt-key"),
            ListItem(Label(f"PTT Mode: {mode_label}"), id="item-ptt-mode"),
            id="settings-list",
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "item-ptt-key":
            current_key: str = getattr(self.app, "_ptt_key", "f9")
            self.app.push_screen(PttKeyScreen(current_key), self._on_ptt_key)
        elif event.item.id == "item-ptt-mode":
            self._cycle_ptt_mode()

    def _on_ptt_key(self, new_key: str | None) -> None:
        """Callback from PttKeyScreen.  Forward the chosen key to the app."""
        if new_key is not None:
            self.dismiss(new_key)
        # else: user cancelled — stay on SettingsScreen

    def _cycle_ptt_mode(self) -> None:
        current = getattr(self.app, "_ptt_mode", "toggle")
        new_mode = "hold" if current == "toggle" else "toggle"
        self.app._ptt_mode = new_mode
        from client.settings import save_settings
        save_settings({
            "ptt_key": getattr(self.app, "_ptt_key", "f9"),
            "ptt_mode": new_mode,
        })
        mode_label = "Toggle" if new_mode == "toggle" else "Hold"
        self.query_one("#item-ptt-mode", ListItem).query_one(Label).update(
            f"PTT Mode: {mode_label}"
        )


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
