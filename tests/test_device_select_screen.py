"""
Unit tests for client/screens/device_select_screen.py.

Tests:
  - DeviceSelectScreen lists input-capable devices for kind="input"
  - DeviceSelectScreen lists output-capable devices for kind="output"
  - Selecting System Default returns ""
  - Selecting a named device returns the device name
  - Escape returns None (cancel)
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from textual.app import App
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

_MOCK_DEVICES = [
    {"name": "Default Input",   "max_input_channels": 2, "max_output_channels": 0},
    {"name": "USB Headset Mic", "max_input_channels": 1, "max_output_channels": 0},
    {"name": "Speakers",        "max_input_channels": 0, "max_output_channels": 2},
    {"name": "Headphones",      "max_input_channels": 0, "max_output_channels": 2},
    {"name": "Loopback",        "max_input_channels": 1, "max_output_channels": 1},
]


@unittest.skipUnless(TEXTUAL_AVAILABLE, "textual not available")
class TestDeviceSelectScreenInput(unittest.IsolatedAsyncioTestCase):

    async def _run(self, kind: str, action):
        """Push DeviceSelectScreen and return the dismissed value after action()."""
        from client.screens.device_select_screen import DeviceSelectScreen
        from textual.widgets import ListView

        result_holder = []

        class _TestApp(App):
            def on_mount(self):
                self.push_screen(DeviceSelectScreen(kind), result_holder.append)

        app = _TestApp()
        with patch("sounddevice.query_devices", return_value=_MOCK_DEVICES), \
             patch("sounddevice.query_hostapis", return_value=[]):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                # Ensure ListView has focus
                try:
                    app.screen.query_one(ListView).focus()
                    await pilot.pause()
                except Exception:
                    pass
                await action(pilot)
                await pilot.pause()

        return result_holder[0] if result_holder else None

    async def test_input_screen_lists_input_devices(self):
        """Input picker should list System Default + 3 input-capable devices."""
        from client.screens.device_select_screen import DeviceSelectScreen
        from textual.widgets import ListView

        class _TestApp(App):
            def on_mount(self):
                self.push_screen(DeviceSelectScreen("input"))

        app = _TestApp()
        with patch("sounddevice.query_devices", return_value=_MOCK_DEVICES), \
             patch("sounddevice.query_hostapis", return_value=[]):
            async with app.run_test() as pilot:
                # Extra pauses: device list is now loaded asynchronously via worker
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                lv = screen.query_one(ListView)
                # System Default + Default Input + USB Headset Mic + Loopback = 4
                self.assertEqual(len(lv), 4)

    async def test_output_screen_lists_output_devices(self):
        """Output picker should list System Default + 3 output-capable devices."""
        from client.screens.device_select_screen import DeviceSelectScreen
        from textual.widgets import ListView

        class _TestApp(App):
            def on_mount(self):
                self.push_screen(DeviceSelectScreen("output"))

        app = _TestApp()
        with patch("sounddevice.query_devices", return_value=_MOCK_DEVICES), \
             patch("sounddevice.query_hostapis", return_value=[]):
            async with app.run_test() as pilot:
                # Extra pauses: device list is now loaded asynchronously via worker
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                lv = screen.query_one(ListView)
                # System Default + Speakers + Headphones + Loopback = 4
                self.assertEqual(len(lv), 4)

    async def test_escape_returns_none(self):
        """Pressing Escape should dismiss with None."""
        async def action(pilot):
            await pilot.press("escape")

        result = await self._run("input", action)
        self.assertIsNone(result)

    async def test_select_system_default_returns_empty_string(self):
        """Selecting System Default (index 0) should dismiss with ''."""
        from client.screens.device_select_screen import DeviceSelectScreen

        result_holder = []

        class _TestApp(App):
            def on_mount(self):
                self.push_screen(DeviceSelectScreen("input"), result_holder.append)

        app = _TestApp()
        with patch("sounddevice.query_devices", return_value=_MOCK_DEVICES), \
             patch("sounddevice.query_hostapis", return_value=[]):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                from textual.widgets import ListItem
                item = screen.query_one("#device-0", ListItem)
                screen.on_list_view_selected(
                    type("E", (), {"item": item})()
                )
                await pilot.pause()

        self.assertEqual(result_holder[0] if result_holder else None, "")

    async def test_select_named_device_returns_name(self):
        """Selecting a named device (index 1) should dismiss with its name."""
        from client.screens.device_select_screen import DeviceSelectScreen

        result_holder = []

        class _TestApp(App):
            def on_mount(self):
                self.push_screen(DeviceSelectScreen("input"), result_holder.append)

        app = _TestApp()
        with patch("sounddevice.query_devices", return_value=_MOCK_DEVICES), \
             patch("sounddevice.query_hostapis", return_value=[]):
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                screen = app.screen
                from textual.widgets import ListItem
                item = screen.query_one("#device-1", ListItem)
                screen.on_list_view_selected(
                    type("E", (), {"item": item})()
                )
                await pilot.pause()

        self.assertEqual(result_holder[0] if result_holder else None, "Default Input")


if __name__ == "__main__":
    unittest.main()
