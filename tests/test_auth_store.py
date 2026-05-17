"""
Unit tests for server/auth_store.py.
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
class TestLoad(unittest.TestCase):

    def test_returns_none_for_absent_file(self):
        self.assertIsNone(auth_store.load("/nonexistent/path/users.json"))

    def test_returns_none_for_none_path(self):
        self.assertIsNone(auth_store.load(None))

    def test_returns_none_for_empty_path(self):
        self.assertIsNone(auth_store.load(""))

    def test_loads_valid_file(self):
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
        data = {"alice": hashed}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            store = auth_store.load(path)
            self.assertIsNotNone(store)
            self.assertIn("alice", store)
        finally:
            os.unlink(path)


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestVerify(unittest.TestCase):

    def setUp(self):
        hashed = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
        self.store = {"alice": hashed}

    def test_correct_password_returns_true(self):
        self.assertTrue(auth_store.verify(self.store, "alice", "correct"))

    def test_wrong_password_returns_false(self):
        self.assertFalse(auth_store.verify(self.store, "alice", "wrong"))

    def test_unknown_username_returns_false(self):
        self.assertFalse(auth_store.verify(self.store, "nobody", "correct"))

    def test_empty_password_returns_false(self):
        self.assertFalse(auth_store.verify(self.store, "alice", ""))


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAddUser(unittest.TestCase):

    def test_creates_file_and_entry(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "mypassword")
            self.assertTrue(os.path.exists(path))
            store = auth_store.load(path)
            self.assertIn("alice", store)
            self.assertTrue(auth_store.verify(store, "alice", "mypassword"))

    def test_overwrites_existing_entry(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "first")
            auth_store.add_user(path, "alice", "second")
            store = auth_store.load(path)
            self.assertFalse(auth_store.verify(store, "alice", "first"))
            self.assertTrue(auth_store.verify(store, "alice", "second"))

    def test_preserves_other_users(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "alicepass")
            auth_store.add_user(path, "bob", "bobpass")
            store = auth_store.load(path)
            self.assertTrue(auth_store.verify(store, "alice", "alicepass"))
            self.assertTrue(auth_store.verify(store, "bob", "bobpass"))

    def test_stored_hash_starts_with_2b(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "users.json")
            auth_store.add_user(path, "alice", "pass")
            with open(path) as f:
                raw = json.load(f)
            self.assertTrue(raw["alice"]["hash"].startswith("$2b$"))


if __name__ == "__main__":
    unittest.main()
