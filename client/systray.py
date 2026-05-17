from __future__ import annotations

import os
import sys
from pathlib import Path


def _icon_dir() -> Path:
    """Return the directory containing the systray PNG assets."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "SystrayIcons"
    return Path(__file__).parent.parent / "Art" / "SystrayIcons"


def _compute_tray_state(
    connection_state: str,
    voice_channel: str,
    transmitting: bool,
    vad_active: bool,
    has_peers: bool,
) -> str:
    """Map application state to one of six tray icon state names.

    Priority order (highest wins):
      1. Not connected          → disconnected
      2. Transmitting + peers   → speaking_and_listening
      3. Transmitting, no peers → speaking
      4. VAD monitoring         → listening
      5. In voice, mic idle     → voice_connected
      6. Connected, no voice    → connected
    """
    if connection_state != "connected":
        return "disconnected"
    if not voice_channel:
        return "connected"
    if transmitting:
        return "speaking_and_listening" if has_peers else "speaking"
    if vad_active:
        return "listening"
    return "voice_connected"


_ICON_FILES: dict[str, str] = {
    "disconnected":           "Disconnected.png",
    "connected":              "Connected.png",
    "voice_connected":        "VoiceConnected.png",
    "listening":              "Listening.png",
    "speaking":               "Speaking.png",
    "speaking_and_listening": "SpeakingAndListening.png",
}

SYSTRAY_AVAILABLE = False

try:
    import pystray
    from PIL import Image as _PILImage

    class SystrayManager:
        """Manages the OS system tray icon lifetime and state."""

        def __init__(self) -> None:
            icon_dir = _icon_dir()
            self._images: dict[str, _PILImage.Image] = {
                state: _PILImage.open(icon_dir / filename)
                for state, filename in _ICON_FILES.items()
            }
            self._state = "disconnected"
            self._icon = pystray.Icon(
                "traxus",
                self._images["disconnected"],
                "Traxus",
                menu=pystray.Menu(
                    pystray.MenuItem("Quit", self._on_quit),
                ),
            )

        def _on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
            icon.stop()
            os._exit(0)

        def start(self) -> None:
            try:
                self._icon.run_detached()
            except Exception:
                pass

        def stop(self) -> None:
            try:
                self._icon.stop()
            except Exception:
                pass

        def set_state(self, state: str) -> None:
            if state == self._state:
                return
            self._state = state
            img = self._images.get(state, self._images["disconnected"])
            try:
                self._icon.icon = img
            except Exception:
                pass

    SYSTRAY_AVAILABLE = True

except Exception:
    class SystrayManager:  # type: ignore[no-redef]
        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def set_state(self, state: str) -> None:
            pass
