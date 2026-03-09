"""
Unit tests for shared/voice_protocol.py — pack_c2s / unpack_s2c round-trip
and edge cases.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.voice_protocol import pack_c2s, unpack_s2c


class TestPackC2S(unittest.TestCase):

    def test_pack_includes_channel_length(self):
        frame = pack_c2s("lounge", b"\x00\x01")
        self.assertEqual(frame[0], len("lounge"))

    def test_pack_includes_channel_name(self):
        frame = pack_c2s("lounge", b"\x00\x01")
        self.assertEqual(frame[1:7], b"lounge")

    def test_pack_includes_pcm(self):
        pcm = b"\x01\x02\x03\x04"
        frame = pack_c2s("ch", pcm)
        self.assertEqual(frame[3:], pcm)

    def test_pack_empty_pcm(self):
        frame = pack_c2s("gen", b"")
        n = frame[0]
        self.assertEqual(frame[1 + n:], b"")

    def test_pack_long_channel_name(self):
        name = "a" * 32
        frame = pack_c2s(name, b"\xff")
        self.assertEqual(frame[0], 32)
        self.assertEqual(frame[1:33], name.encode())


class TestUnpackS2C(unittest.TestCase):

    def _make_s2c(self, channel: str, username: str, pcm: bytes) -> bytes:
        ch = channel.encode()
        un = username.encode()
        return bytes([len(ch)]) + ch + bytes([len(un)]) + un + pcm

    def test_round_trip_channel(self):
        frame = self._make_s2c("lounge", "alice", b"\x10\x20")
        channel, _, _ = unpack_s2c(frame)
        self.assertEqual(channel, "lounge")

    def test_round_trip_username(self):
        frame = self._make_s2c("lounge", "alice", b"\x10\x20")
        _, username, _ = unpack_s2c(frame)
        self.assertEqual(username, "alice")

    def test_round_trip_pcm(self):
        pcm = b"\xAA\xBB\xCC\xDD"
        frame = self._make_s2c("ch", "bob", pcm)
        _, _, result = unpack_s2c(frame)
        self.assertEqual(result, pcm)

    def test_empty_pcm_returns_empty_bytes(self):
        frame = self._make_s2c("gen", "user", b"")
        _, _, pcm = unpack_s2c(frame)
        self.assertEqual(pcm, b"")

    def test_empty_frame_raises(self):
        with self.assertRaises(ValueError):
            unpack_s2c(b"")

    def test_truncated_channel_raises(self):
        # Says channel is 10 bytes but frame only has 3
        with self.assertRaises(ValueError):
            unpack_s2c(bytes([10]) + b"abc")

    def test_truncated_username_raises(self):
        ch = b"ch"
        # Says username is 20 bytes but nothing follows
        frame = bytes([len(ch)]) + ch + bytes([20]) + b"ab"
        with self.assertRaises(ValueError):
            unpack_s2c(frame)


if __name__ == "__main__":
    unittest.main()
