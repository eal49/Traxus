"""
Tests for client/settings.py — load_settings and save_settings.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import client.settings as settings_module


class TestLoadSettings(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent" / "settings.json"
            with patch.object(settings_module, "_SETTINGS_FILE", fake_path):
                result = settings_module.load_settings()
        self.assertEqual(result["ptt_key"], "f9")

    def test_malformed_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "settings.json"
            f.write_text("not valid json", encoding="utf-8")
            with patch.object(settings_module, "_SETTINGS_FILE", f):
                result = settings_module.load_settings()
        self.assertEqual(result["ptt_key"], "f9")

    def test_valid_file_returns_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "settings.json"
            f.write_text(json.dumps({"ptt_key": "f8"}), encoding="utf-8")
            with patch.object(settings_module, "_SETTINGS_FILE", f):
                result = settings_module.load_settings()
        self.assertEqual(result["ptt_key"], "f8")

    def test_non_dict_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "settings.json"
            f.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            with patch.object(settings_module, "_SETTINGS_FILE", f):
                result = settings_module.load_settings()
        self.assertEqual(result["ptt_key"], "f9")


class TestSaveSettings(unittest.TestCase):
    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"ptt_key": "f8"})
            self.assertTrue(f.exists())

    def test_values_are_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"ptt_key": "f10"})
            data = json.loads(f.read_text(encoding="utf-8"))
        self.assertEqual(data["ptt_key"], "f10")

    def test_directory_is_created_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "nested" / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"ptt_key": "f9"})
            self.assertTrue(config_dir.is_dir())
            self.assertTrue(f.exists())


class TestNickColorSetting(unittest.TestCase):
    def test_nick_color_default_is_empty_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent" / "settings.json"
            with patch.object(settings_module, "_SETTINGS_FILE", fake_path):
                result = settings_module.load_settings()
        self.assertEqual(result["nick_color"], "")

    def test_nick_color_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"nick_color": "#ff5500"})
                result = settings_module.load_settings()
        self.assertEqual(result["nick_color"], "#ff5500")

    def test_nick_color_empty_string_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"nick_color": ""})
                result = settings_module.load_settings()
        self.assertEqual(result["nick_color"], "")


class TestJitterBufferFramesSetting(unittest.TestCase):
    def test_default_is_5_when_key_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent" / "settings.json"
            with patch.object(settings_module, "_SETTINGS_FILE", fake_path):
                result = settings_module.load_settings()
        self.assertEqual(result["jitter_buffer_frames"], 5)

    def test_custom_value_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "settings.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_SETTINGS_FILE", f):
                settings_module.save_settings({"jitter_buffer_frames": 5})
                result = settings_module.load_settings()
        self.assertEqual(result["jitter_buffer_frames"], 5)


class TestLoadHistory(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent" / "command_history.json"
            with patch.object(settings_module, "_HISTORY_FILE", fake_path):
                result = settings_module.load_history()
        self.assertEqual(result, [])

    def test_corrupt_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "command_history.json"
            f.write_text("not valid json", encoding="utf-8")
            with patch.object(settings_module, "_HISTORY_FILE", f):
                result = settings_module.load_history()
        self.assertEqual(result, [])

    def test_non_list_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "command_history.json"
            f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
            with patch.object(settings_module, "_HISTORY_FILE", f):
                result = settings_module.load_history()
        self.assertEqual(result, [])

    def test_valid_file_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "command_history.json"
            entries = ["/join #dev", "/nick alice"]
            f.write_text(json.dumps(entries), encoding="utf-8")
            with patch.object(settings_module, "_HISTORY_FILE", f):
                result = settings_module.load_history()
        self.assertEqual(result, entries)

    def test_non_string_entries_filtered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "command_history.json"
            f.write_text(json.dumps(["/cmd", 42, None, "/other"]), encoding="utf-8")
            with patch.object(settings_module, "_HISTORY_FILE", f):
                result = settings_module.load_history()
        self.assertEqual(result, ["/cmd", "/other"])


class TestSaveHistory(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "command_history.json"
            entries = ["/join #dev", "/nick alice"]
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_HISTORY_FILE", f):
                settings_module.save_history(entries)
                result = settings_module.load_history()
        self.assertEqual(result, entries)

    def test_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "nested" / "traxus"
            f = config_dir / "command_history.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_HISTORY_FILE", f):
                settings_module.save_history(["/cmd"])
            self.assertTrue(config_dir.is_dir())
            self.assertTrue(f.exists())

    def test_atomic_write_no_tmp_left_behind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "command_history.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_HISTORY_FILE", f):
                settings_module.save_history(["/cmd"])
            tmp_files = list(config_dir.glob("*.tmp"))
            self.assertEqual(tmp_files, [])

    def test_empty_list_round_trips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "traxus"
            f = config_dir / "command_history.json"
            with patch.object(settings_module, "_CONFIG_DIR", config_dir), \
                 patch.object(settings_module, "_HISTORY_FILE", f):
                settings_module.save_history([])
                result = settings_module.load_history()
        self.assertEqual(result, [])


class TestVadSensitivityScreenEntryPoint(unittest.TestCase):
    def test_settings_screen_has_open_vad_sensitivity_screen(self):
        from client.screens.settings_screen import SettingsScreen
        self.assertTrue(
            hasattr(SettingsScreen, "_open_vad_sensitivity_screen"),
            "_open_vad_sensitivity_screen must exist on SettingsScreen",
        )

    def test_settings_screen_does_not_have_cycle_vad_sensitivity(self):
        from client.screens.settings_screen import SettingsScreen
        self.assertFalse(
            hasattr(SettingsScreen, "_cycle_vad_sensitivity"),
            "_cycle_vad_sensitivity must be removed from SettingsScreen",
        )


if __name__ == "__main__":
    unittest.main()
