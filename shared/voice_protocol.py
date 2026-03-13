"""
Binary frame helpers for voice audio transport.

C2S audio frame layout (with codec tag):
  [1 byte : channel name length N]
  [N bytes: channel name (UTF-8)]
  [1 byte : codec tag (CODEC_RAW=0, CODEC_ADPCM=1)]
  [remaining: audio payload (PCM or ADPCM)]

S2C audio frame layout (with codec tag):
  [1 byte : channel name length N]
  [N bytes: channel name (UTF-8)]
  [1 byte : username length M]
  [M bytes: username (UTF-8)]
  [1 byte : codec tag (CODEC_RAW=0, CODEC_ADPCM=1)]
  [remaining: audio payload (PCM or ADPCM)]
"""
from __future__ import annotations

from shared.adpcm import CODEC_ADPCM, CODEC_RAW  # noqa: F401 (re-exported)


def pack_c2s(channel: str, audio_bytes: bytes, codec: int = CODEC_ADPCM) -> bytes:
    """Pack a C2S binary audio frame."""
    ch = channel.encode()
    return bytes([len(ch)]) + ch + bytes([codec]) + audio_bytes


def unpack_s2c(frame: bytes) -> tuple[str, str, int, bytes]:
    """Unpack an S2C binary audio frame.

    Returns (channel, username, codec, audio_bytes).
    Raises ValueError on malformed frames.
    """
    if not frame:
        raise ValueError("Empty frame")
    n = frame[0]
    if len(frame) < 1 + n + 1:
        raise ValueError("Frame too short for channel header")
    channel = frame[1:1 + n].decode()
    m = frame[1 + n]
    if len(frame) < 1 + n + 1 + m + 1:
        raise ValueError("Frame too short for username header")
    username = frame[2 + n:2 + n + m].decode()
    codec    = frame[2 + n + m]
    audio_bytes = frame[3 + n + m:]
    return channel, username, codec, audio_bytes
