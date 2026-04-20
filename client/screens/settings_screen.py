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

from client.audio_engine import AUDIO_AVAILABLE

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
            "input_device": getattr(app, "_input_device", None),
            "output_device": getattr(app, "_output_device", None),
        })
        return settings

    def _nick_color_label(self) -> str:
        color = getattr(self.app, "_nick_color", "")
        return f"Nick Color: {color if color else 'default'}"

    def _input_device_label(self) -> str:
        dev = getattr(self.app, "_input_device", None)
        return f"Input Device: {dev if dev else 'System Default'}"

    def _output_device_label(self) -> str:
        dev = getattr(self.app, "_output_device", None)
        return f"Output Device: {dev if dev else 'System Default'}"

    def _sens_label(self) -> str:
        thr = int(getattr(self.app, "_vad_custom_threshold", 250))
        return f"VAD Threshold: {thr}"

    def compose(self) -> ComposeResult:
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        mode_label = _PTT_MODE_LABELS.get(current_mode, "Toggle")
        yield Label("Settings", id="settings-title")
        yield ListView(
            ListItem(Label("PTT Key"), id="item-ptt-key"),
            ListItem(Label(f"PTT Mode: {mode_label}"), id="item-ptt-mode"),
            ListItem(Label(self._sens_label()), id="item-vad-sensitivity"),
            ListItem(Label(self._nick_color_label()), id="item-nick-color"),
            ListItem(Label(self._input_device_label()), id="item-input-device"),
            ListItem(Label(self._output_device_label()), id="item-output-device"),
            ListItem(Label("Test Microphone"), id="item-mic-test"),
            id="settings-list",
        )

    def on_mount(self) -> None:
        self._update_vad_sensitivity_visibility()
        self._update_device_visibility()
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
        self.query_one("#item-nick-color", ListItem).query_one(Label).update(
            self._nick_color_label()
        )
        self.query_one("#item-input-device", ListItem).query_one(Label).update(
            self._input_device_label()
        )
        self.query_one("#item-output-device", ListItem).query_one(Label).update(
            self._output_device_label()
        )
        self._update_vad_sensitivity_visibility()
        self._update_device_visibility()
        self._update_mic_test_visibility()

    def _update_vad_sensitivity_visibility(self) -> None:
        current_mode = getattr(self.app, "_ptt_mode", "toggle")
        self.query_one("#item-vad-sensitivity", ListItem).display = (current_mode == "vad")

    def _update_device_visibility(self) -> None:
        self.query_one("#item-input-device", ListItem).display = AUDIO_AVAILABLE
        self.query_one("#item-output-device", ListItem).display = AUDIO_AVAILABLE

    def _update_mic_test_visibility(self) -> None:
        self.query_one("#item-mic-test", ListItem).display = AUDIO_AVAILABLE

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item.id == "item-ptt-key":
            current_key: str = getattr(self.app, "_ptt_key", "f9")
            self.app.push_screen(PttKeyScreen(current_key), self._on_ptt_key)
        elif event.item.id == "item-ptt-mode":
            self._cycle_ptt_mode()
        elif event.item.id == "item-vad-sensitivity":
            self._open_vad_sensitivity_screen()
        elif event.item.id == "item-nick-color":
            self._open_color_picker()
        elif event.item.id == "item-input-device":
            self._open_device_picker("input")
        elif event.item.id == "item-output-device":
            self._open_device_picker("output")
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

    def _open_vad_sensitivity_screen(self) -> None:
        from client.screens.vad_sensitivity_screen import VadSensitivityScreen
        thr = getattr(self.app, "_vad_custom_threshold", 250.0)
        self.app.push_screen(VadSensitivityScreen(thr), self._on_vad_sensitivity_result)

    def _on_vad_sensitivity_result(self, result: float | None) -> None:
        if result is not None:
            from client.settings import save_settings
            self.app._vad_sensitivity = "custom"
            self.app._vad_custom_threshold = result
            save_settings(self._all_settings())
            self._rebuild_settings_list()
            self._restart_vad_if_active()

    def _open_color_picker(self) -> None:
        from client.screens.color_picker_screen import ColorPickerScreen
        current = getattr(self.app, "_nick_color", "")
        self.app.push_screen(ColorPickerScreen(current), self._on_color_picked)

    def _on_color_picked(self, result: str | None) -> None:
        if result is not None:
            self.app._set_nick_color(result)  # type: ignore[attr-defined]
        self._rebuild_settings_list()

    def _open_device_picker(self, kind: str) -> None:
        from client.screens.device_select_screen import DeviceSelectScreen
        self.app.push_screen(
            DeviceSelectScreen(kind),  # type: ignore[arg-type]
            lambda result: self._on_device_selected(kind, result),
        )

    def _on_device_selected(self, kind: str, result: "str | None") -> None:
        if result is None:
            return  # cancelled
        device = result if result else None  # "" → None (System Default)
        if kind == "input":
            self.app._restart_input_device(device)  # type: ignore[attr-defined]
        else:
            self.app._restart_output_device(device)  # type: ignore[attr-defined]
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
