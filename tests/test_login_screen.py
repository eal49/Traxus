"""
Unit tests for client/screens/login_screen.py — password field and auth payload.
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from textual.testing import Pilot
    import textual  # noqa: F401
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


@unittest.skipUnless(TEXTUAL_AVAILABLE, "textual not installed")
class TestLoginScreenPasswordField(unittest.IsolatedAsyncioTestCase):
    """LoginScreen must render a password field that is not persisted."""

    async def test_password_field_present(self):
        from client.app import TraxusApp
        from textual.widgets import Input

        app = TraxusApp()
        async with app.run_test() as pilot:
            inputs = app.query(Input)
            ids = [i.id for i in inputs]
            self.assertIn("password-input", ids)

    async def test_password_field_is_masked(self):
        from client.app import TraxusApp
        from textual.widgets import Input

        app = TraxusApp()
        async with app.run_test() as pilot:
            pw_input = app.query_one("#password-input", Input)
            self.assertTrue(pw_input.password)

    async def test_blank_password_omits_key_from_auth_payload(self):
        """When password field is empty, auth message must not include 'password' key."""
        from client.app import TraxusApp
        from textual.widgets import Input, Button

        captured_payloads = []

        async def fake_connect(url, username, password=""):
            auth: dict = {"type": "auth", "username": username, "version": "x"}
            if password:
                auth["password"] = password
            captured_payloads.append(auth)

        app = TraxusApp()
        async with app.run_test() as pilot:
            app.connect_to_server = fake_connect  # type: ignore[method-assign]
            await pilot.click("#server-input")
            await pilot.type("ws://localhost:8765")
            await pilot.click("#nick-input")
            await pilot.type("alice")
            # Leave password-input empty
            await pilot.click("#connect-btn")
            await pilot.pause()

        self.assertTrue(len(captured_payloads) > 0)
        self.assertNotIn("password", captured_payloads[0])

    async def test_filled_password_included_in_auth_payload(self):
        """When password is typed, auth message must include 'password' key."""
        from client.app import TraxusApp
        from textual.widgets import Input, Button

        captured_payloads = []

        async def fake_connect(url, username, password=""):
            auth: dict = {"type": "auth", "username": username, "version": "x"}
            if password:
                auth["password"] = password
            captured_payloads.append(auth)

        app = TraxusApp()
        async with app.run_test() as pilot:
            app.connect_to_server = fake_connect  # type: ignore[method-assign]
            await pilot.click("#server-input")
            await pilot.type("ws://localhost:8765")
            await pilot.click("#nick-input")
            await pilot.type("alice")
            await pilot.click("#password-input")
            await pilot.type("mysecret")
            await pilot.click("#connect-btn")
            await pilot.pause()

        self.assertTrue(len(captured_payloads) > 0)
        self.assertIn("password", captured_payloads[0])
        self.assertEqual(captured_payloads[0]["password"], "mysecret")

    async def test_password_not_in_settings_after_connect(self):
        """settings.save() must never receive a 'password' key."""
        from client.app import TraxusApp
        from textual.widgets import Input, Button

        saved_settings: list[dict] = []

        def fake_save(data: dict) -> None:
            saved_settings.append(dict(data))

        app = TraxusApp()
        async with app.run_test() as pilot:
            with patch("client.screens.login_screen.save_settings", side_effect=fake_save):
                with patch.object(app, "connect_to_server", return_value=None):
                    await pilot.click("#server-input")
                    await pilot.type("ws://localhost:8765")
                    await pilot.click("#nick-input")
                    await pilot.type("alice")
                    await pilot.click("#password-input")
                    await pilot.type("secret")
                    await pilot.click("#connect-btn")
                    await pilot.pause()

        for call in saved_settings:
            self.assertNotIn("password", call)


if __name__ == "__main__":
    unittest.main()
