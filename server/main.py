"""
Traxus server entry point.

Usage:
    python -m server.main
    TRAXUS_HOST=0.0.0.0 TRAXUS_PORT=9000 python -m server.main
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

# Windows: websockets asyncio server requires SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import websockets
import websockets.asyncio.server

from server.connection_manager import ConnectionManager
from server.channel_registry import ChannelRegistry
from server.message_router import MessageRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("traxus.server")

conn_mgr = ConnectionManager()
chan_reg  = ChannelRegistry()
router   = MessageRouter(conn_mgr, chan_reg)


async def client_handler(ws: websockets.asyncio.server.ServerConnection) -> None:
    client = None
    try:
        async for raw in ws:
            if isinstance(raw, bytes):
                if client is not None:
                    await router.relay_voice(raw, ws, client)
                continue
            client = await router.dispatch(raw, ws, client)
    except websockets.exceptions.ConnectionClosedOK:
        pass
    except websockets.exceptions.ConnectionClosedError as exc:
        log.warning("Connection closed with error: %s", exc)
    except Exception as exc:
        log.exception("Unhandled error in client_handler: %s", exc)
    finally:
        if client is not None:
            await router.on_disconnect(client)


async def main() -> None:
    host = os.getenv("TRAXUS_HOST", "localhost")
    port = int(os.getenv("TRAXUS_PORT", "8765"))

    async with websockets.asyncio.server.serve(client_handler, host, port):
        log.info("Traxus server listening on ws://%s:%d", host, port)
        log.info("Press Ctrl+C to stop.")
        await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server stopped.")
