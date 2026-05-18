"""
Traxus server entry point.

Usage:
    python -m server.main
    TRAXUS_HOST=0.0.0.0 TRAXUS_PORT=9000 python -m server.main
    TRAXUS_DB=/data/traxus.db python -m server.main
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
from server.database import DatabaseAdapter
from server.message_router import MessageRouter
from server import auth_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("traxus.server")


async def main() -> None:
    host = os.getenv("TRAXUS_HOST", "localhost")
    port = int(os.getenv("TRAXUS_PORT", "8765"))
    db_path = os.getenv("TRAXUS_DB", "./traxus.db")

    # Load credential store (None = no-auth mode).
    users_path = os.getenv("TRAXUS_USERS")
    credential_store = None
    if users_path:
        credential_store = auth_store.load(users_path)
        if credential_store is None:
            log.warning("TRAXUS_USERS=%r — file not found; starting in no-auth mode", users_path)
        else:
            log.info("Auth enabled: %d user(s) loaded from %s", len(credential_store), users_path)

    db = DatabaseAdapter(db_path)
    await db.open()
    log.info("Database: %s", db_path)

    chan_reg = ChannelRegistry(db)
    await chan_reg.load()

    conn_mgr = ConnectionManager()
    router = MessageRouter(conn_mgr, chan_reg, credential_store, users_path)

    async def client_handler(ws: websockets.asyncio.server.ServerConnection) -> None:
        client = None
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue  # audio is P2P via WebRTC; binary frames are ignored
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

    try:
        async with websockets.asyncio.server.serve(client_handler, host, port):
            log.info("Traxus server listening on ws://%s:%d", host, port)
            log.info("Press Ctrl+C to stop.")
            await asyncio.get_running_loop().create_future()  # run forever
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Server stopped.")
