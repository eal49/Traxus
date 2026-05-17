"""
Tests for new auth_store functionality: migration, must_change flag,
change_password, get_must_change, and adduser --permanent flag.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from server import auth_store


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestMigration(unittest.TestCase):
    """load() transparently migrates old flat { username: hash } entries."""

    def _make_flat_file(self, d: str) -> str:
        hashed = bcrypt.hashpw(b"flatpass", bcrypt.gensalt()).decode()
        path = os.path.join(d, "users.json")
        with open(path, "w") as f:
            json.dump({"alice": hashed}, f)
        return path

    def test_flat_entry_normalised_to_dict(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_flat_file(d)
            store = auth_store.load(path)
            self.assertIsInstance(store["alice"], dict)
            self.assertIn("hash", store["alice"])

    def test_flat_entry_must_change_defaults_false(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_flat_file(d)
            store = auth_store.load(path)
            self.assertFalse(store["alice"]["must_change"])

    def test_flat_entry_still_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_flat_file(d)
            store = auth_store.load(path)
            self.assertTrue(auth_store.verify(store, "alice", "flatpass"))

    def test_file_not_rewritten_during_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_flat_file(d)
            mtime_before = os.path.getmtime(path)
            auth_store.load(path)
            self.assertEqual(mtime_before, os.path.getmtime(path))


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAddUserMustChange(unittest.TestCase):

    def test_default_must_change_is_true(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "alicepassword")
            store = auth_store.load(path)
            self.assertTrue(store["alice"]["must_change"])

    def test_permanent_sets_must_change_false(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "alicepassword", must_change=False)
            store = auth_store.load(path)
            self.assertFalse(store["alice"]["must_change"])


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestGetMustChange(unittest.TestCase):

    def setUp(self):
        hashed = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
        self.store = {
            "alice": {"hash": hashed, "must_change": True},
            "bob":   {"hash": hashed, "must_change": False},
        }

    def test_returns_true_when_set(self):
        self.assertTrue(auth_store.get_must_change(self.store, "alice"))

    def test_returns_false_when_not_set(self):
        self.assertFalse(auth_store.get_must_change(self.store, "bob"))

    def test_returns_false_for_unknown_user(self):
        self.assertFalse(auth_store.get_must_change(self.store, "nobody"))


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestChangePassword(unittest.TestCase):

    def _make_store(self, d: str, username: str, password: str, must_change: bool = True) -> str:
        path = os.path.join(d, "users.json")
        auth_store.add_user(path, username, password, must_change=must_change)
        return path

    def test_success_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            result = auth_store.change_password(path, "alice", "oldpassword1", "newpassword2")
            self.assertIsNone(result)

    def test_new_password_verifies_after_change(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            auth_store.change_password(path, "alice", "oldpassword1", "newpassword2")
            store = auth_store.load(path)
            self.assertTrue(auth_store.verify(store, "alice", "newpassword2"))

    def test_old_password_no_longer_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            auth_store.change_password(path, "alice", "oldpassword1", "newpassword2")
            store = auth_store.load(path)
            self.assertFalse(auth_store.verify(store, "alice", "oldpassword1"))

    def test_clears_must_change_flag(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1", must_change=True)
            auth_store.change_password(path, "alice", "oldpassword1", "newpassword2")
            store = auth_store.load(path)
            self.assertFalse(store["alice"]["must_change"])

    def test_wrong_old_password_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            result = auth_store.change_password(path, "alice", "wrongpassword", "newpassword2")
            self.assertEqual(result, "wrong_password")

    def test_wrong_old_password_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            mtime_before = os.path.getmtime(path)
            auth_store.change_password(path, "alice", "wrongpassword", "newpassword2")
            self.assertEqual(mtime_before, os.path.getmtime(path))

    def test_new_password_too_short_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            result = auth_store.change_password(path, "alice", "oldpassword1", "short")
            self.assertEqual(result, "too_short")

    def test_new_password_exactly_10_chars_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            result = auth_store.change_password(path, "alice", "oldpassword1", "abcdefghij")
            self.assertIsNone(result)

    def test_same_password_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_store(d, "alice", "oldpassword1")
            result = auth_store.change_password(path, "alice", "oldpassword1", "oldpassword1")
            self.assertEqual(result, "same_password")


if __name__ == "__main__":
    unittest.main()
