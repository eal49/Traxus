"""
Binary frame helpers for voice audio transport.

C2S audio frame layout:
  [1 byte : channel name length N]
  [N bytes: channel name (UTF-8)]
  [remaining: int16 LE PCM samples]

S2C audio frame layout:
  [1 byte : channel name length N]
  [N bytes: channel name (UTF-8)]
  [1 byte : username length M]
  [M bytes: username (UTF-8)]
  [remaining: int16 LE PCM samples]
"""
from __future__ import annotations


def pack_c2s(channel: str, pcm_bytes: bytes) -> bytes:
    """Pack a C2S binary audio frame."""
    ch = channel.encode()
    return bytes([len(ch)]) + ch + pcm_bytes


def unpack_s2c(frame: bytes) -> tuple[str, str, bytes]:
    """Unpack an S2C binary audio frame.

    Returns (channel, username, pcm_bytes).
    Raises ValueError on malformed frames.
    """
    if not frame:
        raise ValueError("Empty frame")
    n = frame[0]
    if len(frame) < 1 + n + 1:
        raise ValueError("Frame too short for channel header")
    channel = frame[1:1 + n].decode()
    m = frame[1 + n]
    if len(frame) < 1 + n + 1 + m:
        raise ValueError("Frame too short for username header")
    username = frame[2 + n:2 + n + m].decode()
    pcm_bytes = frame[2 + n + m:]
    return channel, username, pcm_bytes
