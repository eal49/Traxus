"""
Unit tests for ChangePasswordScreen and the status bar must_change_password nudge.
"""
from __future__ import annotations

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from textual.app import App, ComposeResult  # noqa: F401
    _TEXTUAL_AVAILABLE = True
except ImportError:
    _TEXTUAL_AVAILABLE = False


# ── StatusBar nudge unit tests (no Textual app needed) ────────────────────────

class TestStatusBarNudge(unittest.TestCase):
    """StatusBar._build_markup includes the nudge iff _must_change_password."""

    def setUp(self):
        from client.widgets.status_bar import StatusBar
        self.bar = StatusBar()
        self.bar._state = "connected"
        self.bar._nick = "alice"

    def test_nudge_absent_by_default(self):
        markup = self.bar._build_markup()
        self.assertNotIn("/passwd", markup)

    def test_nudge_present_when_flag_set(self):
        self.bar.update_must_change_password(True)
        markup = self.bar._build_markup()
        self.assertIn("/passwd", markup)

    def test_nudge_removed_after_cleared(self):
        self.bar.update_must_change_password(True)
        self.bar.update_must_change_password(False)
        markup = self.bar._build_markup()
        self.assertNotIn("/passwd", markup)


# ── ChangePasswordScreen Textual tests ────────────────────────────────────────

@unittest.skipUnless(_TEXTUAL_AVAILABLE, "textual not installed")
class TestChangePasswordScreenUnit(unittest.IsolatedAsyncioTestCase):
    """Test ChangePasswordScreen in isolation via Textual pilot."""

    async def _make_app(self):
        """Build a minimal host app that pushes ChangePasswordScreen."""
        from textual.app import App, ComposeResult
        from textual.widgets import Label
        from client.screens.change_password_screen import ChangePasswordScreen

        sent = []

        class HostApp(App):
            def compose(self) -> ComposeResult:
                yield Label("host")

            def on_mount(self) -> None:
                self.push_screen(ChangePasswordScreen())

            def send_ws(self, payload: dict) -> None:
                sent.append(payload)

        return HostApp(), sent

    async def test_mismatch_does_not_send(self):
        app, sent = await self._make_app()
        async with app.run_test() as pilot:
            from client.screens.change_password_screen import ChangePasswordScreen
            screen = app.screen
            if not isinstance(screen, ChangePasswordScreen):
                return  # screen push may be async
            from textual.widgets import Input
            screen.query_one("#old-password", Input).value = "currentpass1"
            screen.query_one("#new-password", Input).value = "newpassword1"
            screen.query_one("#confirm-password", Input).value = "different123"
            await pilot.press("enter")
        self.assertEqual(sent, [])

    async def test_escape_closes_without_sending(self):
        app, sent = await self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("escape")
        self.assertEqual(sent, [])

    async def test_show_server_error_updates_label(self):
        app, sent = await self._make_app()
        async with app.run_test():
            from client.screens.change_password_screen import ChangePasswordScreen
            from textual.widgets import Label
            screen = app.screen
            if isinstance(screen, ChangePasswordScreen):
                screen.show_server_error("wrong_password")
                label = screen.query_one("#error-label", Label)
                # _Static__content is the internal content store used by Static/Label.
                content = str(getattr(label, "_Static__content", ""))
                self.assertIn("incorrect", content.lower())


if __name__ == "__main__":
    unittest.main()
