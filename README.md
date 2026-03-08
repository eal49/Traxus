# Traxus

 Terminal first audio/text chat application. Python + Textual TUI client, asyncio WebSocket server.

## Quick Start

```bash
pip install -r requirements.txt

# Terminal 1 — start server
python -m server.main

# Terminal 2+ — start client(s)
python -m client.main
```

Enter the server address (`ws://localhost:8765`) and a username in the login screen, then press **Connect**.

## Documentation

| Document | Description |
|---|---|
| [docs/commands.md](docs/commands.md) | All slash commands — syntax, arguments, server effects, error conditions |
| [docs/protocol.md](docs/protocol.md) | Full WebSocket protocol — every C2S and S2C message type with field tables and lifecycle diagram |
| [docs/server-rules.md](docs/server-rules.md) | Server business rules — auth guard, validation constraints, broadcast scope, state invariants |

## Running Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## Project Structure

```
traxus/
├── shared/message_types.py   # C2S / S2C protocol constants
├── server/                   # asyncio WebSocket server
│   ├── main.py
│   ├── connection_manager.py
│   ├── channel_registry.py
│   └── message_router.py
├── client/                   # Textual TUI client
│   ├── app.py
│   ├── ws_worker.py
│   ├── commands.py
│   ├── screens/
│   └── widgets/
├── tests/                    # unittest test suite (167 tests)
└── docs/                     # Developer reference documentation
```
