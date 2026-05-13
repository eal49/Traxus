"""
Unit tests for server/adduser.py.

getpass.getpass is patched so tests run non-interactively.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import bcrypt  # noqa: F401
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from server.adduser import main
from server import auth_store


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAdduserMain(unittest.TestCase):

    def test_missing_env_var_exits_1(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRAXUS_USERS", None)
            result = main(["alice"])
        self.assertEqual(result, 1)

    def test_missing_username_arg_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            with patch.dict(os.environ, {"TRAXUS_USERS": path}):
                result = main([])
        self.assertEqual(result, 1)

    def test_empty_password_loops_then_accepts(self):
        # First call returns empty (rejected), second call returns valid pair.
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            with patch.dict(os.environ, {"TRAXUS_USERS": path}):
                with patch(
                    "getpass.getpass",
                    side_effect=["", "validpass", "validpass"],
                ):
                    result = main(["alice"])
            self.assertEqual(result, 0)
            store = auth_store.load(path)
            self.assertTrue(auth_store.verify(store, "alice", "validpass"))

    def test_password_mismatch_loops_then_accepts(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            with patch.dict(os.environ, {"TRAXUS_USERS": path}):
                with patch(
                    "getpass.getpass",
                    side_effect=["pass1", "pass2", "pass1", "pass1"],
                ):
                    result = main(["bob"])
            self.assertEqual(result, 0)
            store = auth_store.load(path)
            self.assertTrue(auth_store.verify(store, "bob", "pass1"))

    def test_successful_write(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            with patch.dict(os.environ, {"TRAXUS_USERS": path}):
                with patch("getpass.getpass", side_effect=["secret", "secret"]):
                    result = main(["carol"])
            self.assertEqual(result, 0)
            store = auth_store.load(path)
            self.assertIsNotNone(store)
            self.assertIn("carol", store)
            self.assertTrue(auth_store.verify(store, "carol", "secret"))


if __name__ == "__main__":
    unittest.main()
