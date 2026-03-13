"""
IMA ADPCM codec for Traxus voice audio.

Wire constants
--------------
CODEC_RAW   = 0x00  raw int16 LE PCM (fallback when numpy unavailable)
CODEC_ADPCM = 0x01  IMA ADPCM compressed

Frame layout produced by encode()
----------------------------------
  [2 bytes : predictor (int16 LE)]
  [2 bytes : step_index (int16 LE)]
  [N bytes : nibble-packed ADPCM samples (two 4-bit nibbles per byte)]

Round-trip: encode then decode restores the original signal shape with
RMS error < 5 % of original RMS (mild quantisation noise only).
"""
from __future__ import annotations

import struct

import numpy as np

CODEC_RAW   = 0
CODEC_ADPCM = 1

# IMA ADPCM step-size table (89 entries)
_STEP_TABLE = np.array([
        7,    8,    9,   10,   11,   12,   13,   14,
       16,   17,   19,   21,   23,   25,   28,   31,
       34,   37,   41,   45,   50,   55,   60,   66,
       73,   80,   88,   97,  107,  118,  130,  143,
      157,  173,  190,  209,  230,  253,  279,  307,
      337,  371,  408,  449,  494,  544,  598,  658,
      724,  796,  876,  963, 1060, 1166, 1282, 1411,
     1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
     3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484,
     7132, 7845, 8630, 9493,10442,11487,12635,13899,
    15289,16818,18500,20350,22385,24623,27086,29794,
    32767,
], dtype=np.int32)

# Index adjustment table (one entry per nibble value 0-15)
_INDEX_TABLE = np.array([
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8,
], dtype=np.int32)


def encode(pcm_bytes: bytes) -> bytes:
    """Encode int16 LE PCM bytes to IMA ADPCM.

    Returns a bytes object with a 4-byte state header followed by packed
    nibbles.  Empty input returns empty bytes.
    """
    if not pcm_bytes:
        return b""

    samples = np.frombuffer(pcm_bytes, dtype="<i2").astype(np.int32)
    n = len(samples)

    predictor  = int(samples[0])
    step_index = 0
    step       = int(_STEP_TABLE[step_index])

    nibbles: list[int] = []

    for s in samples:
        s = int(s)
        delta = s - predictor

        nibble = 0
        if delta < 0:
            nibble = 8
            delta  = -delta

        # Quantise delta against current step
        code = 0
        diff = step >> 3
        if delta >= step:
            code  |= 4
            delta -= step
            diff  += step
        step >>= 1
        if delta >= step:
            code  |= 2
            delta -= step
            diff  += step
        step >>= 1
        if delta >= step:
            code  |= 1
            diff  += step

        nibble |= code
        nibbles.append(nibble)

        if nibble & 8:
            predictor -= diff
        else:
            predictor += diff
        predictor = max(-32768, min(32767, predictor))

        step_index = int(np.clip(step_index + _INDEX_TABLE[nibble], 0, 88))
        step       = int(_STEP_TABLE[step_index])

    # Pack two nibbles per byte (little-endian nibble order)
    out_len   = (n + 1) // 2
    out_bytes = bytearray(out_len)
    for i in range(0, n, 2):
        lo = nibbles[i]
        hi = nibbles[i + 1] if i + 1 < n else 0
        out_bytes[i // 2] = lo | (hi << 4)

    header = struct.pack("<hh", samples[0], 0)  # predictor, step_index=0
    return header + bytes(out_bytes)


def decode(adpcm_bytes: bytes) -> bytes:
    """Decode IMA ADPCM bytes to int16 LE PCM.

    Returns empty bytes for empty input.
    """
    if not adpcm_bytes:
        return b""

    if len(adpcm_bytes) < 4:
        raise ValueError("ADPCM frame too short (need at least 4-byte header)")

    predictor, step_index = struct.unpack_from("<hh", adpcm_bytes, 0)
    predictor  = int(predictor)
    step_index = int(np.clip(step_index, 0, 88))
    step       = int(_STEP_TABLE[step_index])

    payload = adpcm_bytes[4:]
    samples: list[int] = []

    for byte in payload:
        for shift in (0, 4):
            nibble = (byte >> shift) & 0x0F

            diff = step >> 3
            if nibble & 4:
                diff += step
            if nibble & 2:
                diff += step >> 1
            if nibble & 1:
                diff += step >> 2

            if nibble & 8:
                predictor -= diff
            else:
                predictor += diff
            predictor = max(-32768, min(32767, predictor))

            step_index = int(np.clip(step_index + _INDEX_TABLE[nibble], 0, 88))
            step       = int(_STEP_TABLE[step_index])

            samples.append(predictor)

    return np.array(samples, dtype="<i2").tobytes()
