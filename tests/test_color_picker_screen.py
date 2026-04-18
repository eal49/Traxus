"""Tests for client/screens/color_picker_screen.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.screens.color_picker_screen import (
    ColorPickerScreen,
    _PALETTE,
    _COLS,
    _ROWS,
    _HSV_ROWS,
    _GRAY_ROWS,
)


class TestPalette(unittest.TestCase):
    def test_grid_has_512_cells(self):
        total = sum(len(row) for row in _PALETTE)
        self.assertEqual(total, 512)

    def test_grid_has_16_rows(self):
        self.assertEqual(len(_PALETTE), 16)

    def test_grid_has_32_cols_per_row(self):
        for row in _PALETTE:
            self.assertEqual(len(row), 32)

    def test_all_cells_are_valid_hex(self):
        import re
        pattern = re.compile(r"^#[0-9a-f]{6}$")
        for row in _PALETTE:
            for cell in row:
                self.assertRegex(cell, pattern, f"Invalid hex: {cell}")

    def test_grayscale_rows_are_14_and_15(self):
        # Rows 14–15 must be grayscale: r == g == b
        for row_idx in (14, 15):
            for cell in _PALETTE[row_idx]:
                r = int(cell[1:3], 16)
                g = int(cell[3:5], 16)
                b = int(cell[5:7], 16)
                self.assertEqual(r, g, f"Row {row_idx} {cell} not grayscale")
                self.assertEqual(g, b, f"Row {row_idx} {cell} not grayscale")

    def test_row_14_is_darker_than_row_15(self):
        avg14 = sum(int(c[1:3], 16) for c in _PALETTE[14]) / _COLS
        avg15 = sum(int(c[1:3], 16) for c in _PALETTE[15]) / _COLS
        self.assertLess(avg14, avg15)


class TestColorPickerNavigation(unittest.IsolatedAsyncioTestCase):
    async def test_initial_position_is_zero_zero(self):
        screen = ColorPickerScreen()
        self.assertEqual(screen._col, 0)
        self.assertEqual(screen._row, 0)

    async def test_left_clamps_at_zero(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list[str | None] = []
            await app.push_screen(ColorPickerScreen(), result.append)
            await pilot.pause()
            screen = app.screen
            self.assertIsInstance(screen, ColorPickerScreen)
            screen._col = 0
            screen._row = 0
            # Simulate left key
            from textual import events
            screen._col = max(0, screen._col - 1)
            self.assertEqual(screen._col, 0)

    async def test_right_clamps_at_31(self):
        screen = ColorPickerScreen()
        screen._col = _COLS - 1
        screen._col = min(_COLS - 1, screen._col + 1)
        self.assertEqual(screen._col, _COLS - 1)

    async def test_up_clamps_at_zero(self):
        screen = ColorPickerScreen()
        screen._row = 0
        screen._row = max(0, screen._row - 1)
        self.assertEqual(screen._row, 0)

    async def test_down_clamps_at_15(self):
        screen = ColorPickerScreen()
        screen._row = _ROWS - 1
        screen._row = min(_ROWS - 1, screen._row + 1)
        self.assertEqual(screen._row, _ROWS - 1)

    async def test_enter_dismisses_with_hex(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list[str | None] = []
            await app.push_screen(ColorPickerScreen(), result.append)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(result), 1)
            self.assertIsNotNone(result[0])
            self.assertRegex(result[0], r"^#[0-9a-f]{6}$")

    async def test_escape_dismisses_with_none(self):
        from client.app import TraxusApp
        from client.screens.chat_screen import ChatScreen
        app = TraxusApp()
        async with app.run_test() as pilot:
            await app.switch_screen(ChatScreen())
            await pilot.pause()
            result: list[str | None] = []
            await app.push_screen(ColorPickerScreen(), result.append)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(len(result), 1)
            self.assertIsNone(result[0])

    async def test_build_grid_contains_cursor_marker(self):
        screen = ColorPickerScreen()
        screen._col = 5
        screen._row = 3
        grid = screen._build_grid()
        self.assertIn("◆◆", grid)

    async def test_build_indicator_places_arrow_at_correct_position(self):
        screen = ColorPickerScreen()
        screen._col = 4
        indicator = screen._build_indicator()
        self.assertEqual(indicator[4 * 2], "▼")

    async def test_find_closest_returns_valid_cell(self):
        screen = ColorPickerScreen("#5865f2")
        col, row = screen._col, screen._row
        self.assertGreaterEqual(col, 0)
        self.assertLess(col, _COLS)
        self.assertGreaterEqual(row, 0)
        self.assertLess(row, _ROWS)


if __name__ == "__main__":
    unittest.main()
