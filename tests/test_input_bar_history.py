"""
Tests for InputBar slash-command history (Up/Down navigation, persistence, dedup, cap).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import client.settings as settings_module
from client.widgets.input_bar import InputBar


def _make_bar(history: list[str] | None = None) -> InputBar:
    """Return a bare InputBar with history state initialised (no Textual runtime)."""
    bar = InputBar.__new__(InputBar)
    bar._history = list(history) if history is not None else []
    bar._history_pos = None
    bar._draft = ""
    return bar


class _FakeInput:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.cursor_position = 0


class TestHistoryUpNavigation(unittest.TestCase):
    def test_up_recalls_most_recent(self):
        bar = _make_bar(["/join #dev", "/nick alice"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(inp.value, "/nick alice")

    def test_up_saves_draft_on_first_press(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput("partial")
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(bar._draft, "partial")

    def test_repeated_up_steps_back(self):
        bar = _make_bar(["/join #dev", "/nick alice", "/vjoin lounge"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(inp.value, "/vjoin lounge")
        bar._history_up()
        self.assertEqual(inp.value, "/nick alice")
        bar._history_up()
        self.assertEqual(inp.value, "/join #dev")

    def test_up_at_oldest_is_noop(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(inp.value, "/join #dev")
        bar._history_up()
        self.assertEqual(inp.value, "/join #dev")
        self.assertEqual(bar._history_pos, 0)

    def test_up_when_empty_history_is_noop(self):
        bar = _make_bar([])
        inp = _FakeInput("hello")
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(inp.value, "hello")
        self.assertIsNone(bar._history_pos)

    def test_up_sets_cursor_at_end(self):
        bar = _make_bar(["/nick alice"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(inp.cursor_position, len("/nick alice"))


class TestHistoryDownNavigation(unittest.TestCase):
    def _navigate_back(self, bar: InputBar, inp: _FakeInput, n: int) -> None:
        for _ in range(n):
            bar._history_up()

    def test_down_steps_forward(self):
        bar = _make_bar(["/join #dev", "/nick alice"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        bar._history_up()
        self.assertEqual(inp.value, "/join #dev")
        bar._history_down()
        self.assertEqual(inp.value, "/nick alice")

    def test_down_past_newest_restores_draft(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput("my draft")
        bar._input = lambda: inp
        bar._history_up()
        bar._history_down()
        self.assertEqual(inp.value, "my draft")
        self.assertIsNone(bar._history_pos)

    def test_down_when_not_in_history_is_noop(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput("hello")
        bar._input = lambda: inp
        bar._history_down()
        self.assertEqual(inp.value, "hello")

    def test_down_when_empty_history_is_noop(self):
        bar = _make_bar([])
        inp = _FakeInput("hello")
        bar._input = lambda: inp
        bar._history_down()
        self.assertEqual(inp.value, "hello")

    def test_down_sets_cursor_at_end(self):
        bar = _make_bar(["/join #dev", "/nick alice", "/vjoin lounge"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()   # → /vjoin lounge (newest)
        bar._history_up()   # → /nick alice
        bar._history_down() # → /vjoin lounge (history entry, not draft)
        self.assertEqual(inp.cursor_position, len("/vjoin lounge"))


class TestHistorySubmitRecording(unittest.TestCase):
    def _submit(self, bar: InputBar, text: str) -> None:
        """Simulate the recording part of on_input_submitted (without Textual)."""
        if text.startswith("/"):
            if not bar._history or bar._history[-1] != text:
                bar._history.append(text)
                if len(bar._history) > settings_module.MAX_HISTORY:
                    bar._history = bar._history[-settings_module.MAX_HISTORY:]
        bar._history_pos = None
        bar._draft = ""

    def test_slash_command_added_to_history(self):
        bar = _make_bar()
        self._submit(bar, "/join #dev")
        self.assertEqual(bar._history, ["/join #dev"])

    def test_plain_message_not_added_to_history(self):
        bar = _make_bar()
        self._submit(bar, "hello world")
        self.assertEqual(bar._history, [])

    def test_consecutive_duplicate_suppressed(self):
        bar = _make_bar()
        self._submit(bar, "/vjoin lounge")
        self._submit(bar, "/vjoin lounge")
        self.assertEqual(bar._history, ["/vjoin lounge"])

    def test_non_consecutive_duplicate_kept(self):
        bar = _make_bar()
        self._submit(bar, "/vjoin lounge")
        self._submit(bar, "/nick alice")
        self._submit(bar, "/vjoin lounge")
        self.assertEqual(bar._history, ["/vjoin lounge", "/nick alice", "/vjoin lounge"])

    def test_history_capped_at_max(self):
        bar = _make_bar()
        for i in range(settings_module.MAX_HISTORY + 1):
            self._submit(bar, f"/cmd {i}")
        self.assertEqual(len(bar._history), settings_module.MAX_HISTORY)
        self.assertEqual(bar._history[0], "/cmd 1")
        self.assertEqual(bar._history[-1], f"/cmd {settings_module.MAX_HISTORY}")

    def test_position_reset_after_submit(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput()
        bar._input = lambda: inp
        bar._history_up()
        self.assertIsNotNone(bar._history_pos)
        self._submit(bar, "/nick alice")
        self.assertIsNone(bar._history_pos)

    def test_draft_cleared_after_submit(self):
        bar = _make_bar(["/join #dev"])
        inp = _FakeInput("partial")
        bar._input = lambda: inp
        bar._history_up()
        self.assertEqual(bar._draft, "partial")
        self._submit(bar, "/nick alice")
        self.assertEqual(bar._draft, "")


class TestHistoryPersistence(unittest.TestCase):
    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "command_history.json"
            entries = ["/join #dev", "/nick alice"]
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_HISTORY_FILE", f):
                settings_module.save_history(entries)
                result = settings_module.load_history()
        self.assertEqual(result, entries)


if __name__ == "__main__":
    unittest.main()
