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

from client.audio_engine import AUDIO_AVAILABLE, NS_AVAILABLE

_PTT_MODE_CYCLE = ["toggle", "hold", "vad"]
_PTT_MODE_LABELS = {"toggle": "Toggle", "hold": "Hold", "vad": "VAD"}

_VAD_SENSITIVITY_CYCLE = ["low", "medium", "high", "very_high", "custom"]
_VAD_SENSITIVITY_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "very_high": "Very High",
    "custom": "Custom",
}


class SettingsScreen(ModalScreen[str | None]):
    """Top-level settings menu.  Dismisses with the new PTT key string, or
    None if the user pressed Escape without making a change."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def _all_settings(self) -> dict:
        """Build a complete settings dict — merge app state onto disk to preserve all keys."""
        from client.settings import load_settings
        app = self.app
        settings = load_settings()
        settings.update({
            "ptt_key": getattr(app, "_ptt_key", "f9"),
            "ptt_mode": getattr(app, "_ptt_mode", "toggle"),
            "vad_sensitivity": getattr(app, "_vad_sensitivity", "high"),
            "vad_custom_threshold": getattr(app, "_vad_custom_threshold", 50.0),
            "noise_suppression": getattr(
                getattr(app, "_audio_engine", None), "noise_suppression_enabled", True
            ),
        })
        return settings

    def _ns_label(self) -> str:
        enabled = getattr(
            getattr(self.app, "_audio_engine", None), "noise_suppression_enabled", True
        )
        return f"Noise Suppression: {'On' if enabled else 'Off'}"

    def _sens_label(self) -> str:
        sens = getattr(self.app, "_vad_sensitivity", "high")
        if sens == "custom":
            thr = int(getattr(self.app, "_vad_custom_threshold", 50.0))
            return f"VAD Sensitivity: Custom ({thr})"
        label = _VAD_SENSITIVITY_LABELS.get(sens, "High")
        return f"VAD Sensitivity: {label}"

    def compose(self) -> ComposeResult:
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        mode_label = _PTT_MODE_LABELS.get(current_mode, "Toggle")
        yield Label("Settings", id="settings-title")
        yield ListView(
            ListItem(Label("PTT Key"), id="item-ptt-key"),
            ListItem(Label(f"PTT Mode: {mode_label}"), id="item-ptt-mode"),
            ListItem(Label(self._sens_label()), id="item-vad-sensitivity"),
            ListItem(Label(self._ns_label()), id="item-noise-suppression"),
            ListItem(Label("Test Microphone"), id="item-mic-test"),
            id="settings-list",
        )

    def on_mount(self) -> None:
        self._update_vad_sensitivity_visibility()
        self._update_noise_suppression_visibility()
        self._update_mic_test_visibility()

    def _rebuild_settings_list(self) -> None:
        """Update labels in-place and show/hide conditional items."""
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        mode_label = _PTT_MODE_LABELS.get(current_mode, "Toggle")
        self.query_one("#item-ptt-mode", ListItem).query_one(Label).update(
            f"PTT Mode: {mode_label}"
        )
        self.query_one("#item-vad-sensitivity", ListItem).query_one(Label).update(
            self._sens_label()
        )
        self.query_one("#item-noise-suppression", ListItem).query_one(Label).update(
            self._ns_label()
        )
        self._update_vad_sensitivity_visibility()
        self._update_noise_suppression_visibility()
        self._update_mic_test_visibility()

    def _update_vad_sensitivity_visibility(self) -> None:
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        self.query_one("#item-vad-sensitivity", ListItem).display = (current_mode == "vad")

    def _update_noise_suppression_visibility(self) -> None:
        self.query_one("#item-noise-suppression", ListItem).display = NS_AVAILABLE

    def _update_mic_test_visibility(self) -> None:
        self.query_one("#item-mic-test", ListItem).display = AUDIO_AVAILABLE

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "item-ptt-key":
            current_key: str = getattr(self.app, "_ptt_key", "f9")
            self.app.push_screen(PttKeyScreen(current_key), self._on_ptt_key)
        elif event.item.id == "item-ptt-mode":
            self._cycle_ptt_mode()
        elif event.item.id == "item-vad-sensitivity":
            self._cycle_vad_sensitivity()
        elif event.item.id == "item-noise-suppression":
            self._toggle_noise_suppression()
        elif event.item.id == "item-mic-test":
            self._open_mic_test()

    def _on_ptt_key(self, new_key: str | None) -> None:
        """Callback from PttKeyScreen.  Forward the chosen key to the app."""
        if new_key is not None:
            self.dismiss(new_key)
        # else: user cancelled — stay on SettingsScreen

    def _cycle_ptt_mode(self) -> None:
        from client.settings import save_settings
        current = getattr(self.app, "_ptt_mode", "toggle")
        idx = _PTT_MODE_CYCLE.index(current) if current in _PTT_MODE_CYCLE else 0
        new_mode = _PTT_MODE_CYCLE[(idx + 1) % len(_PTT_MODE_CYCLE)]
        self.app._ptt_mode = new_mode
        save_settings(self._all_settings())
        self._rebuild_settings_list()

    def _cycle_vad_sensitivity(self) -> None:
        from client.settings import save_settings
        current = getattr(self.app, "_vad_sensitivity", "high")
        if current == "custom":
            # Already on custom — open calibration screen
            self._open_calibration()
            return
        idx = _VAD_SENSITIVITY_CYCLE.index(current) if current in _VAD_SENSITIVITY_CYCLE else 2
        new_sens = _VAD_SENSITIVITY_CYCLE[(idx + 1) % len(_VAD_SENSITIVITY_CYCLE)]
        self.app._vad_sensitivity = new_sens
        save_settings(self._all_settings())
        if new_sens == "custom":
            self._open_calibration()
        else:
            self._restart_vad_if_active()
            self._rebuild_settings_list()

    def _toggle_noise_suppression(self) -> None:
        from client.settings import save_settings
        engine = getattr(self.app, "_audio_engine", None)
        if engine is None:
            return
        engine.noise_suppression_enabled = not engine.noise_suppression_enabled
        save_settings(self._all_settings())
        self._rebuild_settings_list()

    def _open_mic_test(self) -> None:
        from client.screens.mic_test_screen import MicTestScreen
        self.app.push_screen(MicTestScreen())

    def _open_calibration(self) -> None:
        from client.screens.vad_calibration_screen import VadCalibrationScreen
        initial = getattr(self.app, "_vad_custom_threshold", 50.0)
        self.app.push_screen(VadCalibrationScreen(initial), self._on_calibration_result)

    def _on_calibration_result(self, threshold: float | None) -> None:
        if threshold is not None:
            from client.settings import save_settings
            self.app._vad_custom_threshold = threshold
            save_settings(self._all_settings())
        self._rebuild_settings_list()
        # Calibration closed the mic stream; restore VAD listening if still needed.
        self._restart_vad_if_active()

    def _restart_vad_if_active(self) -> None:
        """Restart VAD with the current threshold if in VAD mode + voice channel."""
        try:
            if (getattr(self.app, "_ptt_mode", "") == "vad"
                    and getattr(self.app, "current_voice_channel", "")):
                # Stop any active transmission first.
                if getattr(self.app._audio_engine, "transmitting", False):
                    self.app.stop_ptt()
                self.app._exit_vad_listening()
                self.app._enter_vad_listening()
        except Exception:
            pass


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
