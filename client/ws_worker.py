"""
WebSocket worker that runs as an asyncio Task inside Textual's event loop.

The worker owns three concurrent coroutines (via asyncio.gather):
  _recv_loop  — reads from the WebSocket, posts ServerMessage to the app
  _send_loop  — drains the outbound asyncio.Queue
  _ping_loop  — sends a keepalive ping every 30 s

On disconnect it retries with exponential back-off (1 s → 30 s cap).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

import websockets
import websockets.asyncio.client
import websockets.exceptions

from shared.message_types import C2S, VERSION

if TYPE_CHECKING:
    from client.app import TraxusApp

log = logging.getLogger("traxus.worker")

PING_INTERVAL = 30.0
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 30.0


class WsWorker:
    """
    Not a Textual Worker subclass — this is a plain class whose
    `run()` coroutine is passed directly to `app.run_worker()`.
    That schedules it as an asyncio.Task on Textual's own loop,
    so websockets and Textual share the same event loop naturally.
    """

    def __init__(self, app: "TraxusApp") -> None:
        self._app = app
        self._ws: websockets.asyncio.client.ClientConnection | None = None
        self._send_queue: asyncio.Queue[str] = asyncio.Queue()
        self._binary_send_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = False

    # ── Public API (called from Textual event handlers) ───────────────────────

    def enqueue(self, payload: dict) -> None:
        """Queue a message to be sent to the server. Safe from any sync handler."""
        self._send_queue.put_nowait(json.dumps(payload))

    def enqueue_binary(self, data: bytes) -> None:
        """Queue raw bytes to be sent as a binary frame."""
        self._binary_send_queue.put_nowait(data)

    def stop(self) -> None:
        """Signal the worker to stop reconnecting."""
        self._running = False
        if self._ws is not None:
            # Schedule close on the loop — safe from sync context
            asyncio.ensure_future(self._ws.close())

    # ── Main coroutine (passed to app.run_worker) ─────────────────────────────

    async def run(self, url: str, username: str) -> None:
        self._running = True
        delay = BACKOFF_INITIAL

        while self._running:
            try:
                self._post_state("connecting")
                async with websockets.asyncio.client.connect(url) as ws:
                    self._ws = ws
                    delay = BACKOFF_INITIAL          # reset back-off on success

                    # Send auth immediately
                    await ws.send(json.dumps({
                        "type": C2S.AUTH,
                        "username": username,
                        "version": VERSION,
                    }))

                    self._post_state("connected")

                    # Run the three pumps concurrently; any exception cancels all
                    await asyncio.gather(
                        self._recv_loop(ws),
                        self._send_loop(ws),
                        self._ping_loop(ws),
                    )

            except (OSError, websockets.exceptions.WebSocketException) as exc:
                log.warning("WS error: %s — retrying in %.0fs", exc, delay)
                self._post_state("reconnecting", str(exc))
                self._ws = None

                if not self._running:
                    break

                await asyncio.sleep(delay)
                delay = min(delay * 2, BACKOFF_MAX)

            except asyncio.CancelledError:
                break

        self._post_state("disconnected")

    # ── Internal loops ────────────────────────────────────────────────────────

    async def _recv_loop(
        self, ws: websockets.asyncio.client.ClientConnection
    ) -> None:
        async for raw in ws:
            if isinstance(raw, bytes):
                self._post_audio_frame(raw)
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Received non-JSON: %r", raw[:100])
                continue
            # post_message is safe from async code on the same loop
            self._post_server_message(payload)

    async def _send_loop(
        self, ws: websockets.asyncio.client.ClientConnection
    ) -> None:
        text_get = asyncio.ensure_future(self._send_queue.get())
        bin_get  = asyncio.ensure_future(self._binary_send_queue.get())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {text_get, bin_get},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                try:
                    for fut in done:
                        data = fut.result()
                        await ws.send(data)
                        if fut is text_get:
                            text_get = asyncio.ensure_future(self._send_queue.get())
                        else:
                            bin_get = asyncio.ensure_future(self._binary_send_queue.get())
                except websockets.exceptions.WebSocketException:
                    break
        finally:
            text_get.cancel()
            bin_get.cancel()

    async def _ping_loop(
        self, ws: websockets.asyncio.client.ClientConnection
    ) -> None:
        while True:
            await asyncio.sleep(PING_INTERVAL)
            try:
                await ws.send(json.dumps({"type": C2S.PING, "ts": time.time()}))
            except websockets.exceptions.WebSocketException:
                break

    # ── App message helpers ───────────────────────────────────────────────────

    def _post_server_message(self, payload: dict) -> None:
        from client.app import TraxusApp
        self._app.post_message(TraxusApp.ServerMessage(payload))

    def _post_audio_frame(self, data: bytes) -> None:
        from client.app import TraxusApp
        self._app.post_message(TraxusApp.AudioFrame(data))

    def _post_state(self, state: str, detail: str = "") -> None:
        from client.app import TraxusApp
        self._app.post_message(TraxusApp.ConnectionStateChanged(state, detail))
