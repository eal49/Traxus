"""Tests for client/widgets/message_view.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.widgets.message_view import MessageView, _strip_markup


# ── _strip_markup ─────────────────────────────────────────────────────────────

class TestStripMarkup(unittest.TestCase):
    def test_removes_markup_tags(self):
        self.assertEqual(_strip_markup("[bold]hello[/bold]"), "hello")

    def test_plain_text_unchanged(self):
        self.assertEqual(_strip_markup("hello world"), "hello world")

    def test_removes_nested_markup(self):
        self.assertEqual(_strip_markup("[dim][italic]x[/italic][/dim]"), "x")


# ── Payload store ─────────────────────────────────────────────────────────────

class TestPayloadStore(unittest.TestCase):
    def _make_screen(self):
        mv = MessageView.__new__(MessageView)
        mv._lines = []
        mv._payloads = []
        mv._cursor = None
        mv._last_width = 0
        mv.write = lambda *a, **kw: None  # no Textual runtime needed
        return mv

    def test_payloads_length_matches_lines_after_add_chat(self):
        mv = self._make_screen()
        payload = {"username": "alice", "content": "hi", "ts": 1.0}
        mv._emit("markup line", payload)
        self.assertEqual(len(mv._payloads), len(mv._lines))

    def test_system_message_stores_none(self):
        mv = self._make_screen()
        mv._emit("[dim]system[/dim]", None)
        self.assertIsNone(mv._payloads[0])

    def test_multiple_entries_stay_aligned(self):
        mv = self._make_screen()
        p1 = {"msg_id": "a"}
        p2 = None
        p3 = {"msg_id": "b"}
        mv._emit("line 1", p1)
        mv._emit("line 2", p2)
        mv._emit("line 3", p3)
        self.assertEqual(len(mv._lines), 3)
        self.assertEqual(len(mv._payloads), 3)
        self.assertEqual(mv._payloads[0], p1)
        self.assertIsNone(mv._payloads[1])
        self.assertEqual(mv._payloads[2], p3)

    def test_payload_stored_with_add_chat(self):
        mv = self._make_screen()
        payload = {"username": "bob", "content": "hey", "ts": 2.0, "msg_id": "xyz"}
        mv.add_chat(payload)
        self.assertEqual(mv._payloads[0], payload)


# ── Cursor navigation ─────────────────────────────────────────────────────────

class TestCursorNavigation(unittest.TestCase):
    def _make_screen_with_lines(self, n: int = 5):
        mv = MessageView.__new__(MessageView)
        mv._lines = [f"line {i}" for i in range(n)]
        mv._payloads = [{"msg_id": str(i)} for i in range(n)]
        mv._cursor = None
        mv._last_width = 0
        mv._redraw_called = 0

        def _fake_redraw():
            mv._redraw_called += 1

        mv._redraw = _fake_redraw
        mv.clear = lambda: None
        mv.write = lambda *a, **kw: None
        return mv

    def test_enter_selection_mode_sets_cursor_to_last(self):
        mv = self._make_screen_with_lines(5)
        mv.enter_selection_mode()
        self.assertEqual(mv._cursor, 4)

    def test_exit_selection_mode_clears_cursor(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 2
        mv.exit_selection_mode()
        self.assertIsNone(mv._cursor)

    def test_move_cursor_up(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 3
        mv.move_cursor(-1)
        self.assertEqual(mv._cursor, 2)

    def test_move_cursor_down(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 2
        mv.move_cursor(1)
        self.assertEqual(mv._cursor, 3)

    def test_move_cursor_clamps_at_zero(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 0
        mv.move_cursor(-1)
        self.assertEqual(mv._cursor, 0)

    def test_move_cursor_clamps_at_last(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 4
        mv.move_cursor(1)
        self.assertEqual(mv._cursor, 4)

    def test_move_cursor_triggers_redraw(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = 2
        mv.move_cursor(1)
        self.assertEqual(mv._redraw_called, 1)

    def test_move_cursor_when_none_does_nothing(self):
        mv = self._make_screen_with_lines(5)
        mv._cursor = None
        mv.move_cursor(1)
        self.assertIsNone(mv._cursor)
        self.assertEqual(mv._redraw_called, 0)


# ── selected_payload ──────────────────────────────────────────────────────────

class TestSelectedPayload(unittest.TestCase):
    def _make_screen_with_payloads(self):
        mv = MessageView.__new__(MessageView)
        mv._lines = ["line 0", "line 1", "line 2"]
        mv._payloads = [{"msg_id": "a"}, None, {"msg_id": "c"}]
        mv._cursor = None
        return mv

    def test_returns_none_when_cursor_inactive(self):
        mv = self._make_screen_with_payloads()
        self.assertIsNone(mv.selected_payload())

    def test_returns_payload_at_cursor(self):
        mv = self._make_screen_with_payloads()
        mv._cursor = 0
        self.assertEqual(mv.selected_payload(), {"msg_id": "a"})

    def test_returns_none_payload_for_system_line(self):
        mv = self._make_screen_with_payloads()
        mv._cursor = 1
        self.assertIsNone(mv.selected_payload())

    def test_returns_correct_payload_for_last_line(self):
        mv = self._make_screen_with_payloads()
        mv._cursor = 2
        self.assertEqual(mv.selected_payload(), {"msg_id": "c"})


# ── Highlight in redraw ───────────────────────────────────────────────────────

class TestRedrawHighlight(unittest.TestCase):
    def test_cursor_line_wrapped_in_reverse(self):
        mv = MessageView.__new__(MessageView)
        mv._lines = ["[bold]hello[/bold]", "[dim]world[/dim]"]
        mv._payloads = [None, None]
        mv._cursor = 0
        mv._last_width = 80

        written = []
        mv.clear = lambda: None
        mv.write = lambda s: written.append(s)

        mv._redraw()
        self.assertIn("[reverse]", written[0])
        self.assertNotIn("[reverse]", written[1])

    def test_non_cursor_line_not_highlighted(self):
        mv = MessageView.__new__(MessageView)
        mv._lines = ["line A", "line B"]
        mv._payloads = [None, None]
        mv._cursor = 1
        mv._last_width = 80

        written = []
        mv.clear = lambda: None
        mv.write = lambda s: written.append(s)

        mv._redraw()
        self.assertNotIn("[reverse]", written[0])
        self.assertIn("[reverse]", written[1])


if __name__ == "__main__":
    unittest.main()
