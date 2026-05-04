"""
Tests for InputBar Tab/Shift+Tab slash-command completion.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.widgets.input_bar import InputBar


def _make_bar(input_value: str = "") -> tuple[InputBar, "_FakeInput"]:
    bar = InputBar.__new__(InputBar)
    bar._history = []
    bar._history_pos = None
    bar._draft = ""
    bar._completions = []
    bar._completion_pos = None
    bar._completion_prefix = ""
    bar._completing = False
    inp = _FakeInput(input_value)
    bar._input = lambda: inp
    return bar, inp


class _FakeInput:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.cursor_position = 0


class TestTabCompletionSingleMatch(unittest.TestCase):
    def test_single_match_completes_immediately(self):
        bar, inp = _make_bar("/jo")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/join")

    def test_single_match_does_not_enter_cycling(self):
        bar, inp = _make_bar("/jo")
        bar._complete(forward=True)
        self.assertIsNone(bar._completion_pos)

    def test_single_match_sets_cursor_at_end(self):
        bar, inp = _make_bar("/jo")
        bar._complete(forward=True)
        self.assertEqual(inp.cursor_position, len("/join"))

    def test_single_match_no_trailing_space(self):
        bar, inp = _make_bar("/jo")
        bar._complete(forward=True)
        self.assertFalse(inp.value.endswith(" "))


class TestTabCompletionMultipleMatches(unittest.TestCase):
    def test_first_tab_shows_first_candidate(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        # /v matches: vcreate, vjoin, vleave — alphabetically first is vcreate
        self.assertEqual(inp.value, "/vcreate")

    def test_repeated_tab_advances(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/vjoin")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/vleave")

    def test_tab_wraps_from_last_to_first(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)  # vcreate
        bar._complete(forward=True)  # vjoin
        bar._complete(forward=True)  # vleave
        bar._complete(forward=True)  # wraps → vcreate
        self.assertEqual(inp.value, "/vcreate")

    def test_shift_tab_cycles_backward(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)   # enters cycling at vcreate
        bar._complete(forward=False)  # wraps backward → vleave
        self.assertEqual(inp.value, "/vleave")

    def test_shift_tab_from_start_wraps_to_last(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=False)
        # First Shift+Tab: enters cycling at last candidate
        self.assertEqual(inp.value, "/vleave")

    def test_cursor_set_at_end_during_cycling(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertEqual(inp.cursor_position, len(inp.value))

    def test_completion_prefix_saved(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertEqual(bar._completion_prefix, "/v")

    def test_completed_value_no_trailing_space(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertFalse(inp.value.endswith(" "))


class TestTabCompletionNoOp(unittest.TestCase):
    def test_no_match_is_noop(self):
        bar, inp = _make_bar("/xyz")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/xyz")
        self.assertIsNone(bar._completion_pos)

    def test_bare_slash_is_noop(self):
        bar, inp = _make_bar("/")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/")
        self.assertIsNone(bar._completion_pos)

    def test_non_slash_input_is_noop(self):
        bar, inp = _make_bar("hello")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "hello")
        self.assertIsNone(bar._completion_pos)

    def test_empty_input_is_noop(self):
        bar, inp = _make_bar("")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "")
        self.assertIsNone(bar._completion_pos)


class TestEscapeRestoresPrefix(unittest.TestCase):
    def _make_key_event(self, key: str):
        class FakeEvent:
            def __init__(self, k):
                self.key = k
                self._stopped = False
            def stop(self):
                self._stopped = True
        return FakeEvent(key)

    def test_escape_while_cycling_restores_prefix(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertEqual(inp.value, "/vcreate")
        ev = self._make_key_event("escape")
        bar.on_key(ev)
        self.assertEqual(inp.value, "/v")

    def test_escape_while_cycling_resets_state(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        ev = self._make_key_event("escape")
        bar.on_key(ev)
        self.assertIsNone(bar._completion_pos)
        self.assertEqual(bar._completions, [])

    def test_escape_while_cycling_is_consumed(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        ev = self._make_key_event("escape")
        bar.on_key(ev)
        self.assertTrue(ev._stopped)

    def test_escape_outside_cycling_not_consumed(self):
        bar, inp = _make_bar("/v")
        ev = self._make_key_event("escape")
        bar.on_key(ev)
        self.assertFalse(ev._stopped)


class TestTypingExitsCycling(unittest.TestCase):
    def _fake_changed_event(self, bar: InputBar, value: str):
        class FakeInput:
            pass
        class FakeEvent:
            def __init__(self):
                self.value = value
                self.input = FakeInput()
        return FakeEvent()

    def test_user_type_resets_completion_state(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertIsNotNone(bar._completion_pos)
        # Simulate user typing (completing flag is False)
        bar._completing = False
        ev = self._fake_changed_event(bar, "/vc")
        bar.on_input_changed(ev)
        self.assertIsNone(bar._completion_pos)
        self.assertEqual(bar._completions, [])

    def test_programmatic_change_does_not_reset_state(self):
        bar, inp = _make_bar("/v")
        bar._complete(forward=True)
        self.assertIsNotNone(bar._completion_pos)
        # Simulate programmatic change (completing flag is True)
        bar._completing = True
        ev = self._fake_changed_event(bar, "/vcreate")
        bar.on_input_changed(ev)
        # State should survive
        self.assertIsNotNone(bar._completion_pos)
        bar._completing = False


if __name__ == "__main__":
    unittest.main()
