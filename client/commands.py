"""
Client-side slash command parser.

Usage:
    cmd = parse_input("/join random")
    # ParsedCommand(name="join", args=["random"])

    cmd = parse_input("hello world")
    # None  →  plain chat message
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedCommand:
    name: str
    args: list[str]


def parse_input(text: str) -> ParsedCommand | None:
    """Return ParsedCommand if text is a slash command, else None."""
    text = text.strip()
    if not text.startswith("/"):
        return None
    parts = text[1:].split()
    if not parts:
        return None
    return ParsedCommand(name=parts[0].lower(), args=parts[1:])


HELP_TEXT = """\
  /join <channel>     Join or switch to a channel
  /leave <channel>    Leave a channel
  /nick <name>        Change your display name
  /channels           List all available channels
  /create <name>      Create a new text channel
  /vcreate <name>     Create a new voice channel
  /vjoin <channel>    Join a voice channel
  /vleave [channel]   Leave current (or specified) voice channel
  F9 (default)        Toggle push-to-talk (mic) — key or mouse button, change via /settings
  /who                List members in the current channel
  /settings           Open the settings menu (configure PTT key, etc.)
  /color <name|#hex>  Set your nick color (blue/green/red/… or #rrggbb); "reset" to clear
  /quote              Quote a message line (type "/quote " to enter selection mode)
  /pin                Pin a message to the top of the channel (type "/pin " to select)
  /passwd             Change your password (only available when server auth is enabled)
  /audioTest          Send 10 test tones over the active voice channel (latency / pipeline test)
  /help               Show this help
  /quit               Disconnect and exit\
"""

KNOWN_COMMANDS = {
    "join", "leave", "nick", "channels", "create", "who", "help", "quit",
    "vcreate", "vjoin", "vleave", "settings", "color", "quote", "pin",
    "audiotest", "passwd",
}
