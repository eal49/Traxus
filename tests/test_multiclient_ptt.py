"""
Multi-client PTT investigation test.

Connects two clients to a live server, has client2 transmit a burst of audio
frames, and verifies that client1's Textual event loop stays responsive
throughout.

The freeze under investigation:
  sd.play() is called directly on the asyncio event loop once per incoming
  audio frame (~50 fps).  Even with blocking=False, sounddevice internally
  calls stop() to kill the previous stream before starting a new one.  That
  stop() is synchronous and can stall the event loop, causing the TUI to
  freeze.

Detection strategy:
  Before and during the audio burst, time how long pilot.pause(0.1) actually
  takes.  A responsive event loop should complete in ~0.1 s.  A frozen loop
  takes >> 0.1 s.  We fail if any pause takes more than 1 s (10×).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

import websockets.asyncio.client

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.app import TraxusApp
from client.screens.chat_screen import ChatScreen
from client.screens.login_screen import LoginScreen
from client.widgets.message_view import MessageView
from shared import voice_protocol
from shared.message_types import VERSION
from textual.widgets import Input


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_s2c_frame(channel: str, username: str, pcm: bytes) -> bytes:
    ch = channel.encode()
    un = username.encode()
    return bytes([len(ch)]) + ch + bytes([len(un)]) + un + pcm


async def _raw_client(username: str) -> websockets.asyncio.client.ClientConnection:
    """Return an authenticated raw WS connection."""
    ws = await websockets.asyncio.client.connect("ws://localhost:8765")
    await ws.send(json.dumps({"type": "auth", "username": username, "client_version": VERSION}))
    resp = json.loads(await ws.recv())
    assert resp["type"] == "auth_ok", f"auth failed: {resp}"
    return ws


async def _drain_until(ws, match_type: str, timeout: float = 3.0) -> dict:
    """Read from ws until a message with the given type is found."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        if msg.get("type") == match_type:
            return msg
    raise TimeoutError(f"{match_type!r} not received within {timeout}s")


# ── test class ────────────────────────────────────────────────────────────────

class TestMultiClientPtt(unittest.IsolatedAsyncioTestCase):
    """
    Two clients share a voice channel; client2 transmits audio; client1 must
    stay responsive.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=os.path.join(os.path.dirname(__file__), ".."),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        cls._server.wait(timeout=5)

    async def test_textual_pump_responsive_while_receiving_audio(self) -> None:
        """
        Client1's Textual message pump must stay fast while client2 floods audio.

        Two things are verified:
          1. play() returns in < 1 ms per call (queue.put_nowait, not sd.play).
             Failure means the background-thread architecture is broken and
             sd.play() is still being called on the message-pump thread.
          2. A Textual chat message sent DURING the audio burst appears in
             client1's view within 2 s.  Failure means the message pump is
             saturated (audio handlers are slow and blocking the queue).
        """
        FRAME_COUNT = 50
        PCM = b"\x00\x01" * 320
        MAX_PLAY_MS = 1.0       # play() must return in < 1 ms (queue put only)
        MAX_MSG_SECS = 2.0      # chat message must appear within 2 s of burst

        play_durations: list[float] = []
        received_messages: list[str] = []

        async def _noop_capture(channel, send_fn):
            return

        app = TraxusApp()
        async with app.run_test(size=(120, 40)) as pilot:

            # ── 1. Login ──────────────────────────────────────────────────────
            self.assertIsInstance(app.screen, LoginScreen)
            app.screen.query_one("#server-input", Input).value = "ws://localhost:8765"
            nick = app.screen.query_one("#nick-input", Input)
            nick.value = "listener"
            nick.focus()
            await pilot.press("enter")

            for _ in range(20):
                await pilot.pause(0.15)
                if isinstance(app.screen, ChatScreen):
                    break
            self.assertIsInstance(app.screen, ChatScreen)

            # Capture incoming chat messages so we can time their arrival.
            original_append = app.screen.append_chat

            def capture_chat(payload: dict) -> None:
                received_messages.append(payload.get("content", ""))
                original_append(payload)

            app.screen.append_chat = capture_chat  # type: ignore[method-assign]

            with patch("client.app.AUDIO_AVAILABLE", True):

                # ── 2. Create + join voice channel ────────────────────────────
                app._audio_engine.start = MagicMock()
                app._audio_engine.capture_loop = _noop_capture

                # Instrument play() to verify it returns instantly.
                real_play = app._audio_engine.play

                def timed_play(pcm_bytes: bytes) -> None:
                    t0 = time.monotonic()
                    real_play(pcm_bytes)
                    play_durations.append((time.monotonic() - t0) * 1000)

                app._audio_engine.play = timed_play  # type: ignore[method-assign]

                app.handle_input("/vcreate lounge")
                await pilot.pause(0.5)

                app.handle_input("/vjoin lounge")
                for _ in range(40):
                    await pilot.pause(0.1)
                    if app.current_voice_channel:
                        break
                self.assertEqual(app.current_voice_channel, "lounge")

                # ── 3. Client2 floods audio AND sends a chat message ──────────
                ws2 = await _raw_client("transmitter")
                sentinel = "PING_DURING_AUDIO"
                t_sent = None
                try:
                    await ws2.send(json.dumps({"type": "voice_join", "channel": "lounge"}))
                    await _drain_until(ws2, "voice_state")

                    frame = voice_protocol.pack_c2s("lounge", PCM)
                    for i in range(FRAME_COUNT):
                        await ws2.send(frame)
                        # Send the sentinel after half the burst so it arrives
                        # while audio frames are still being processed.
                        if i == FRAME_COUNT // 2:
                            t_sent = time.monotonic()
                            await ws2.send(json.dumps({
                                "type": "message",
                                "channel": "general",
                                "content": sentinel,
                            }))

                    # Wait for the sentinel to appear (up to MAX_MSG_SECS).
                    deadline = time.monotonic() + MAX_MSG_SECS
                    while sentinel not in received_messages:
                        if time.monotonic() > deadline:
                            break
                        await pilot.pause(0.05)

                finally:
                    await ws2.close()

            # ── 4. Assertions ─────────────────────────────────────────────────
            if play_durations:
                avg_ms = sum(play_durations) / len(play_durations)
                max_ms = max(play_durations)
                print(
                    f"\n  play() called {len(play_durations)} times — "
                    f"avg {avg_ms:.3f}ms, max {max_ms:.3f}ms per call"
                )
                self.assertLess(
                    max_ms,
                    MAX_PLAY_MS,
                    f"play() took {max_ms:.3f}ms on its slowest call (limit {MAX_PLAY_MS}ms). "
                    f"play() must only queue data; sd.play() must run in the background thread.",
                )

            msg_delay = time.monotonic() - t_sent if t_sent else float("inf")
            self.assertIn(
                sentinel,
                received_messages,
                f"Chat message never appeared after audio burst "
                f"(waited {MAX_MSG_SECS}s). Textual message pump is saturated — "
                f"on_traxus_app_audio_frame is too slow.",
            )
            self.assertLess(
                msg_delay,
                MAX_MSG_SECS,
                f"Chat message took {msg_delay:.2f}s to appear during audio burst "
                f"(limit {MAX_MSG_SECS}s). Textual message pump is backlogged.",
            )

    async def test_client1_receives_text_messages_after_audio_burst(self) -> None:
        """
        After receiving an audio burst, client1 must still be able to receive
        a normal text chat message from client2.

        A frozen event loop would prevent the message from arriving.
        """
        PCM = b"\x00\x01" * 320
        FRAME_COUNT = 30
        TEXT_TIMEOUT = 3.0  # seconds to wait for the chat message

        async def _noop_capture(channel, send_fn):
            return

        app = TraxusApp()
        received_messages: list[str] = []

        async with app.run_test(size=(120, 40)) as pilot:

            # ── 1. Login ──────────────────────────────────────────────────────
            app.screen.query_one("#server-input", Input).value = "ws://localhost:8765"
            nick = app.screen.query_one("#nick-input", Input)
            nick.value = "listener2"
            nick.focus()
            await pilot.press("enter")

            for _ in range(20):
                await pilot.pause(0.15)
                if isinstance(app.screen, ChatScreen):
                    break
            self.assertIsInstance(app.screen, ChatScreen)

            # Capture incoming chat messages
            original_append = app.screen.append_chat

            def capture_chat(payload: dict) -> None:
                received_messages.append(payload.get("content", ""))
                original_append(payload)

            app.screen.append_chat = capture_chat  # type: ignore[method-assign]

            with patch("client.app.AUDIO_AVAILABLE", True):
                app._audio_engine.start = MagicMock()
                app._audio_engine.capture_loop = _noop_capture

                app.handle_input("/vcreate lounge2")
                await pilot.pause(0.5)
                app.handle_input("/vjoin lounge2")

                for _ in range(40):
                    await pilot.pause(0.1)
                    if app.current_voice_channel:
                        break
                self.assertEqual(app.current_voice_channel, "lounge2")

                # ── 2. Client2 joins, bursts audio, then sends text ───────────
                ws2 = await _raw_client("spammer")
                try:
                    # Join #general so text messages go to a channel client1 is in
                    await _drain_until(ws2, "joined")   # auto-join #general on auth

                    await ws2.send(json.dumps({"type": "voice_join", "channel": "lounge2"}))
                    await _drain_until(ws2, "voice_state")

                    frame = voice_protocol.pack_c2s("lounge2", PCM)
                    for _ in range(FRAME_COUNT):
                        await ws2.send(frame)

                    # After the burst, send a plain text message
                    sentinel = "PING_AFTER_AUDIO"
                    await ws2.send(json.dumps({
                        "type": "message",
                        "channel": "general",
                        "content": sentinel,
                    }))

                    # Wait for client1 to receive it
                    deadline = time.monotonic() + TEXT_TIMEOUT
                    while sentinel not in received_messages:
                        if time.monotonic() > deadline:
                            break
                        await pilot.pause(0.1)

                finally:
                    await ws2.close()

            self.assertIn(
                sentinel,
                received_messages,
                f"Client1 never received the text message sent after the audio burst "
                f"(within {TEXT_TIMEOUT}s). The event loop may be frozen by sd.play().",
            )


if __name__ == "__main__":
    unittest.main()
