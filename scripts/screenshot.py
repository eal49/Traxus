"""
Take a screenshot of the Traxus chat UI.

Starts a real server subprocess, drives the TUI client via Textual's test
pilot, injects demo messages, then exports an SVG screenshot.

Usage:
    python scripts/screenshot.py
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from textual.widgets import Input

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.login_screen import LoginScreen


DEMO_MESSAGES = [
    ("alice",  "hey everyone, server's looking good 🎉"),
    ("bob",    "yeah the new SQLite persistence is great"),
    ("charlie","agreed — history survived the restart earlier"),
    ("alice",  "anyone up for a voice call later?"),
    ("bob",    "sure, I'll join #lounge around 8pm"),
    ("charlie","I'll be there, just need to finish this PR first"),
    ("alice",  "cool, I'll create the channel now"),
    ("bob",    "btw has anyone tried the VAD mode? it actually works"),
    ("charlie","yeah it's surprisingly accurate, barely any false triggers"),
    ("alice",  "I had to tune the sensitivity a bit but once set it's solid"),
]


async def run() -> None:
    server = subprocess.Popen(
        [sys.executable, "-m", "server.main"],
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    try:
        app = TraxusApp()

        async with app.run_test(size=(140, 45)) as pilot:
            assert isinstance(app.screen, LoginScreen)

            app.screen.query_one("#server-input", Input).value = "ws://localhost:8765"
            nick = app.screen.query_one("#nick-input", Input)
            nick.value = "alice"
            nick.focus()
            await pilot.press("enter")

            for _ in range(30):
                await pilot.pause(0.15)
                if isinstance(app.screen, ChatScreen):
                    break

            if not isinstance(app.screen, ChatScreen):
                print("ERROR: did not reach ChatScreen", file=sys.stderr)
                return

            await pilot.pause(0.3)

            # Inject demo messages directly into the MessageView
            chat: ChatScreen = app.screen
            import time as _time
            mv = chat.query_one("MessageView")
            for username, content in DEMO_MESSAGES:
                mv.add_chat({
                    "username": username,
                    "content": content,
                    "ts": _time.time(),
                })
                await pilot.pause(0.05)

            await pilot.pause(0.3)

            path = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshot-chat.svg")
            app.save_screenshot(path)
            print(f"Saved: {os.path.abspath(path)}")

    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    asyncio.run(run())
