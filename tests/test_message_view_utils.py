"""Unit tests for client/widgets/message_view.py utility functions."""
import sys
import os
import time
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.widgets.message_view import _escape, _fmt_ts


class TestEscape(unittest.TestCase):

    def test_plain_text_unchanged(self):
        self.assertEqual(_escape("hello world"), "hello world")

    def test_open_bracket_escaped(self):
        result = _escape("[bold]")
        self.assertIn(r"\[", result)

    def test_close_bracket_escaped(self):
        result = _escape("[bold]text[/bold]")
        self.assertIn(r"\]", result)

    def test_no_brackets_unchanged(self):
        self.assertEqual(_escape("no brackets here"), "no brackets here")

    def test_multiple_brackets_all_escaped(self):
        result = _escape("[a][b][c]")
        self.assertEqual(result.count(r"\["), 3)
        self.assertEqual(result.count(r"\]"), 3)

    def test_nested_markup_escaped(self):
        result = _escape("[bold red]important[/bold red]")
        self.assertTrue(result.startswith(r"\["))

    def test_empty_string(self):
        self.assertEqual(_escape(""), "")

    def test_only_brackets(self):
        result = _escape("[]")
        self.assertEqual(result, r"\[\]")

    def test_unicode_preserved(self):
        text = "héllo wörld [test]"
        result = _escape(text)
        self.assertIn("héllo wörld", result)
        self.assertIn(r"\[", result)

    def test_newlines_preserved(self):
        self.assertEqual(_escape("line1\nline2"), "line1\nline2")

    def test_result_is_string(self):
        self.assertIsInstance(_escape("anything"), str)


class TestFmtTs(unittest.TestCase):

    def test_none_returns_placeholder(self):
        self.assertEqual(_fmt_ts(None), "--:--")

    def test_returns_hh_mm_format(self):
        ts = time.time()
        result = _fmt_ts(ts)
        # Should match HH:MM
        self.assertRegex(result, r"^\d{2}:\d{2}$")

    def test_known_timestamp(self):
        # Use a fixed local time: create a datetime, convert to timestamp
        dt = datetime(2024, 1, 15, 14, 30, 0)
        ts = dt.timestamp()
        result = _fmt_ts(ts)
        self.assertEqual(result, "14:30")

    def test_midnight(self):
        dt = datetime(2024, 6, 1, 0, 0, 0)
        result = _fmt_ts(dt.timestamp())
        self.assertEqual(result, "00:00")

    def test_end_of_day(self):
        dt = datetime(2024, 6, 1, 23, 59, 0)
        result = _fmt_ts(dt.timestamp())
        self.assertEqual(result, "23:59")

    def test_result_is_string(self):
        self.assertIsInstance(_fmt_ts(time.time()), str)

    def test_zero_timestamp_does_not_raise(self):
        # 0 = 1970-01-01 00:00:00 UTC — valid but may show local offset time
        result = _fmt_ts(0.0)
        self.assertRegex(result, r"^\d{2}:\d{2}$")


if __name__ == "__main__":
    unittest.main()
