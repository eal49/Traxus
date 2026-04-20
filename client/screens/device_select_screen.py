"""
DeviceSelectScreen — modal for selecting audio input or output device.

Returns:
  None        — user cancelled (no change)
  ""          — user selected System Default
  "name str"  — user selected a specific device

On Windows, PortAudio exposes each physical device once per host API
(MME, DirectSound, WASAPI). We prefer WASAPI entries; if WASAPI is not
present we fall back to all unique entries by name.
"""
from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView


def _enumerate_devices(kind: str) -> list[str]:
    """Return a deduplicated list of device names for the given kind.

    Prefers WASAPI entries on Windows; falls back to first-seen dedup elsewhere.
    """
    try:
        import sounddevice as sd
        devices = list(sd.query_devices())
        hostapis = sd.query_hostapis()
    except Exception:
        return []

    # Find the WASAPI host API index (Windows only; -1 if absent).
    wasapi_idx = next(
        (i for i, h in enumerate(hostapis) if "wasapi" in h.get("name", "").lower()),
        -1,
    )

    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"

    # First pass: collect WASAPI-only names (or all names if no WASAPI).
    preferred: list[str] = []
    fallback: list[str] = []
    seen_preferred: set[str] = set()
    seen_fallback: set[str] = set()

    for d in devices:
        if d.get(channel_key, 0) <= 0:
            continue
        name = d.get("name", "").strip()
        if not name:
            continue
        if wasapi_idx >= 0 and d.get("hostapi") == wasapi_idx:
            if name not in seen_preferred:
                seen_preferred.add(name)
                preferred.append(name)
        else:
            if name not in seen_fallback:
                seen_fallback.add(name)
                fallback.append(name)

    return preferred if preferred else fallback


class DeviceSelectScreen(ModalScreen["str | None"]):

    BINDINGS = [("escape", "dismiss_cancel", "Cancel")]

    DEFAULT_CSS = """
    DeviceSelectScreen {
        align: center middle;
    }
    #device-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        width: 80;
    }
    #device-list {
        width: 80;
        height: auto;
        max-height: 20;
        border: round $accent;
    }
    #device-hint {
        width: 80;
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, kind: Literal["input", "output"]) -> None:
        super().__init__()
        self._kind = kind
        self._device_names: list[str] = []

    def compose(self) -> ComposeResult:
        label = "Select Input Device" if self._kind == "input" else "Select Output Device"
        yield Label(label, id="device-title")
        yield ListView(id="device-list")
        yield Label("Enter=select  Esc=cancel", id="device-hint")

    def on_mount(self) -> None:
        lv = self.query_one("#device-list", ListView)
        lv.append(ListItem(Label("System Default"), id="device-0"))
        self._device_names = [""]  # index 0 = system default
        self.run_worker(self._load_devices())

    async def _load_devices(self) -> None:
        import asyncio
        loop = asyncio.get_running_loop()
        names = await loop.run_in_executor(None, _enumerate_devices, self._kind)
        try:
            lv = self.query_one("#device-list", ListView)
        except Exception:
            return
        for name in names:
            self._device_names.append(name)
            lv.append(ListItem(Label(name), id=f"device-{len(self._device_names) - 1}"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        try:
            idx = int(item_id.split("-", 1)[1])
            self.dismiss(self._device_names[idx])
        except (ValueError, IndexError):
            self.dismiss(None)

    def action_dismiss_cancel(self) -> None:
        self.dismiss(None)
