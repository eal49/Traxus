"""
Integration tests for the /pin and /quote selection-mode features.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.widgets.message_view import MessageView


# ── Selection mode (unit-level, no Textual pilot needed) ─────────────────────

class TestSelectionModeUnit(unittest.TestCase):
    def _make_mv(self, n_lines=3):
        mv = MessageView.__new__(MessageView)
        mv._lines = [f"line {i}" for i in range(n_lines)]
        mv._payloads = [
            {"msg_id": f"id{i}", "username": "alice", "content": f"msg {i}"}
            for i in range(n_lines)
        ]
        mv._cursor = None
        mv._last_width = 80
        mv.clear = lambda: None
        mv.write = lambda *a, **kw: None
        return mv

    def test_enter_selection_places_cursor_at_last_line(self):
        mv = self._make_mv(4)
        mv.enter_selection_mode()
        self.assertEqual(mv._cursor, 3)

    def test_exit_selection_clears_cursor(self):
        mv = self._make_mv(4)
        mv.enter_selection_mode()
        mv.exit_selection_mode()
        self.assertIsNone(mv._cursor)

    def test_selected_payload_returns_correct_entry(self):
        mv = self._make_mv(3)
        mv._cursor = 1
        p = mv.selected_payload()
        self.assertEqual(p["msg_id"], "id1")

    def test_selected_payload_none_when_no_cursor(self):
        mv = self._make_mv(3)
        self.assertIsNone(mv.selected_payload())

    def test_cursor_moves_and_clamps(self):
        mv = self._make_mv(3)
        mv._cursor = 0
        mv.move_cursor(-1)
        self.assertEqual(mv._cursor, 0)

        mv._cursor = 2
        mv.move_cursor(1)
        self.assertEqual(mv._cursor, 2)


# ── Pin header (Textual pilot) ────────────────────────────────────────────────

class TestPinHeaderViaTextual(unittest.IsolatedAsyncioTestCase):
    async def test_pin_header_hidden_by_default(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        from textual.widgets import Static
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            chat = app.screen
            header = chat.query_one("#pin-header", Static)
            self.assertFalse(header.display)

    async def test_update_pin_shows_header(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        from textual.widgets import Static
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            chat = app.screen
            chat.update_pin({
                "msg_id": "abc",
                "username": "alice",
                "content": "hello world",
            })
            await pilot.pause()
            header = chat.query_one("#pin-header", Static)
            self.assertTrue(header.display)
            # Check content via the Static.content property
            content_str = str(header.content)
            self.assertIn("alice", content_str)
            self.assertIn("hello world", content_str)

    async def test_update_pin_none_hides_header(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        from textual.widgets import Static
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            chat = app.screen
            chat.update_pin({"msg_id": "x", "username": "bob", "content": "hi"})
            await pilot.pause()
            chat.update_pin(None)
            await pilot.pause()
            header = chat.query_one("#pin-header", Static)
            self.assertFalse(header.display)


# ── /quote (Textual pilot) ────────────────────────────────────────────────────

class TestQuoteViaTextual(unittest.IsolatedAsyncioTestCase):
    async def test_quote_populates_input_bar(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        from client.widgets.input_bar import InputBar
        from textual.widgets import Input
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            payload = {
                "msg_id": "abc",
                "username": "alice",
                "content": "hello world",
                "ts": 1.0,
            }
            app._handle_quote(payload, "[dim]some markup[/dim]")
            await pilot.pause()
            chat = app.screen
            inp = chat.query_one("#message-input", Input)
            self.assertEqual(inp.value, "> @alice: hello world › ")

    async def test_quote_system_line_uses_plain_text(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        from textual.widgets import Input
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()

            app._handle_quote(None, "[dim italic]  system message[/dim italic]")
            await pilot.pause()
            chat = app.screen
            inp = chat.query_one("#message-input", Input)
            self.assertTrue(inp.value.startswith("> "))
            self.assertIn("system message", inp.value)


if __name__ == "__main__":
    unittest.main()
