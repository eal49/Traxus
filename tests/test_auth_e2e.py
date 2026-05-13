"""
End-to-end authentication integration tests.

Covers smoke-test 7.2:
  A) Server with TRAXUS_USERS + correct password  → ChatScreen reached
  B) Server with TRAXUS_USERS + wrong password    → LoginScreen stays, error shown
  C) No-auth server (TRAXUS_USERS unset) + no password → ChatScreen reached

Each class spins up its own server subprocess on a dedicated port so the
tests can run safely alongside test_ptt_e2e.py (port 8765).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual.widgets import Input

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.login_screen import LoginScreen

try:
    import bcrypt as _bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

_PORT_AUTH   = 8766   # auth-enabled server (scenarios A + B)
_PORT_NOAUTH = 8767   # no-auth server (scenario C)


def _write_creds(path: str, username: str, password: str) -> None:
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with open(path, "w") as f:
        json.dump({username: hashed}, f)


async def _fill_and_connect(
    pilot,
    app: TraxusApp,
    port: int,
    username: str,
    password: str = "",
) -> None:
    """Fill the login form and click Connect."""
    app.screen.query_one("#server-input", Input).value = f"ws://localhost:{port}"
    app.screen.query_one("#nick-input", Input).value = username
    if password:
        app.screen.query_one("#password-input", Input).value = password
    app.screen.query_one("#nick-input", Input).focus()
    await pilot.press("enter")


async def _wait_for_screen(pilot, screen_type, timeout_s: float = 4.0):
    steps = int(timeout_s / 0.15)
    for _ in range(steps):
        await pilot.pause(0.15)
        if isinstance(pilot.app.screen, screen_type):
            break


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAuthE2EWithCredentials(unittest.IsolatedAsyncioTestCase):
    """Scenarios A and B: server running with a credentials file."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.mkdtemp()
        cls._creds_path = os.path.join(cls._tmpdir, "users.json")
        _write_creds(cls._creds_path, "alice", "hunter2")

        env = os.environ.copy()
        env["TRAXUS_USERS"] = cls._creds_path
        env["TRAXUS_PORT"]  = str(_PORT_AUTH)
        env["TRAXUS_HOST"]  = "127.0.0.1"

        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        cls._server.wait(timeout=5)
        import shutil
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    async def test_a_correct_password_reaches_chat_screen(self):
        """Scenario A: correct credentials → ChatScreen."""
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            self.assertIsInstance(app.screen, LoginScreen)
            await _fill_and_connect(pilot, app, _PORT_AUTH, "alice", "hunter2")
            await _wait_for_screen(pilot, ChatScreen)
            self.assertIsInstance(
                app.screen, ChatScreen,
                "Expected ChatScreen after correct password — stayed on LoginScreen",
            )
            # Drain pending Textual reactive callbacks (e.g. Header.set_title)
            # before the run_test context exits — avoids NoMatches during teardown.
            await pilot.pause(0.3)

    async def test_b_wrong_password_stays_on_login_screen(self):
        """Scenario B: wrong password → LoginScreen remains, error displayed."""
        errors_shown: list[str] = []

        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            self.assertIsInstance(app.screen, LoginScreen)

            # Spy on show_error before triggering the connect attempt.
            login: LoginScreen = app.screen  # type: ignore[assignment]
            _orig = login.show_error
            login.show_error = lambda msg: (errors_shown.append(msg), _orig(msg))[1]  # type: ignore[method-assign]

            await _fill_and_connect(pilot, app, _PORT_AUTH, "alice", "wrongpass")
            # Wait long enough for the server rejection to arrive.
            await _wait_for_screen(pilot, ChatScreen, timeout_s=3.0)
            self.assertIsInstance(
                app.screen, LoginScreen,
                "Expected LoginScreen to remain after wrong password",
            )
            self.assertTrue(
                any("password" in e.lower() for e in errors_shown),
                f"Expected an error message mentioning 'password'; got: {errors_shown}",
            )
            await pilot.pause(0.3)


@unittest.skipUnless(_BCRYPT_AVAILABLE, "bcrypt not installed")
class TestAuthE2ENoAuth(unittest.IsolatedAsyncioTestCase):
    """Scenario C: server without TRAXUS_USERS — password field ignored."""

    @classmethod
    def setUpClass(cls) -> None:
        env = os.environ.copy()
        env.pop("TRAXUS_USERS", None)
        env["TRAXUS_PORT"] = str(_PORT_NOAUTH)
        env["TRAXUS_HOST"] = "127.0.0.1"

        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        cls._server.wait(timeout=5)

    async def test_c_no_password_reaches_chat_screen(self):
        """Scenario C: no-auth server, blank password → ChatScreen."""
        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:
            self.assertIsInstance(app.screen, LoginScreen)
            await _fill_and_connect(pilot, app, _PORT_NOAUTH, "bob")
            await _wait_for_screen(pilot, ChatScreen)
            self.assertIsInstance(
                app.screen, ChatScreen,
                "Expected ChatScreen on no-auth server without password",
            )
            await pilot.pause(0.3)


if __name__ == "__main__":
    unittest.main()
