"""
Unit tests for shared/voice_protocol.py — pack_c2s / unpack_s2c round-trip
and edge cases.

Wire format (post-ADPCM change):
  C2S: [ch_len 1B][channel NB][codec 1B][audio_bytes]
  S2C: [ch_len 1B][channel NB][user_len 1B][username MB][codec 1B][audio_bytes]
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.adpcm import CODEC_ADPCM, CODEC_RAW
from shared.voice_protocol import pack_c2s, unpack_s2c


class TestPackC2S(unittest.TestCase):

    def test_pack_includes_channel_length(self):
        frame = pack_c2s("lounge", b"\x00\x01")
        self.assertEqual(frame[0], len("lounge"))

    def test_pack_includes_channel_name(self):
        frame = pack_c2s("lounge", b"\x00\x01")
        self.assertEqual(frame[1:7], b"lounge")

    def test_pack_codec_byte_position(self):
        # Codec byte sits immediately after the channel name
        channel = "ch"
        frame = pack_c2s(channel, b"\x01\x02", codec=CODEC_ADPCM)
        codec_pos = 1 + len(channel)
        self.assertEqual(frame[codec_pos], CODEC_ADPCM)

    def test_pack_default_codec_is_adpcm(self):
        frame = pack_c2s("ch", b"\x01\x02")
        codec_pos = 1 + len("ch")
        self.assertEqual(frame[codec_pos], CODEC_ADPCM)

    def test_pack_raw_codec(self):
        frame = pack_c2s("ch", b"\x01\x02", codec=CODEC_RAW)
        codec_pos = 1 + len("ch")
        self.assertEqual(frame[codec_pos], CODEC_RAW)

    def test_pack_includes_audio(self):
        audio = b"\x01\x02\x03\x04"
        frame = pack_c2s("ch", audio, codec=CODEC_RAW)
        # audio starts after: ch_len(1) + channel(2) + codec(1) = 4
        self.assertEqual(frame[4:], audio)

    def test_pack_empty_audio(self):
        frame = pack_c2s("gen", b"", codec=CODEC_RAW)
        n = frame[0]
        # after channel: codec byte, then nothing
        self.assertEqual(frame[1 + n + 1:], b"")

    def test_pack_long_channel_name(self):
        name = "a" * 32
        frame = pack_c2s(name, b"\xff", codec=CODEC_RAW)
        self.assertEqual(frame[0], 32)
        self.assertEqual(frame[1:33], name.encode())


class TestUnpackS2C(unittest.TestCase):

    def _make_s2c(
        self, channel: str, username: str, audio: bytes, codec: int = CODEC_RAW
    ) -> bytes:
        ch = channel.encode()
        un = username.encode()
        return bytes([len(ch)]) + ch + bytes([len(un)]) + un + bytes([codec]) + audio

    def test_round_trip_channel(self):
        frame = self._make_s2c("lounge", "alice", b"\x10\x20")
        channel, _, _, _ = unpack_s2c(frame)
        self.assertEqual(channel, "lounge")

    def test_round_trip_username(self):
        frame = self._make_s2c("lounge", "alice", b"\x10\x20")
        _, username, _, _ = unpack_s2c(frame)
        self.assertEqual(username, "alice")

    def test_round_trip_codec_raw(self):
        frame = self._make_s2c("ch", "bob", b"\xAA", codec=CODEC_RAW)
        _, _, codec, _ = unpack_s2c(frame)
        self.assertEqual(codec, CODEC_RAW)

    def test_round_trip_codec_adpcm(self):
        frame = self._make_s2c("ch", "bob", b"\xAA", codec=CODEC_ADPCM)
        _, _, codec, _ = unpack_s2c(frame)
        self.assertEqual(codec, CODEC_ADPCM)

    def test_round_trip_audio(self):
        audio = b"\xAA\xBB\xCC\xDD"
        frame = self._make_s2c("ch", "bob", audio)
        _, _, _, result = unpack_s2c(frame)
        self.assertEqual(result, audio)

    def test_empty_audio_returns_empty_bytes(self):
        frame = self._make_s2c("gen", "user", b"")
        _, _, _, audio = unpack_s2c(frame)
        self.assertEqual(audio, b"")

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

    def test_codec_byte_position_in_s2c(self):
        # Verify codec byte sits at correct position in S2C frame
        channel = "lounge"
        username = "alice"
        frame = self._make_s2c(channel, username, b"\x01\x02", codec=CODEC_ADPCM)
        # Position: ch_len(1) + channel(6) + user_len(1) + username(5) = 13
        codec_pos = 1 + len(channel) + 1 + len(username)
        self.assertEqual(frame[codec_pos], CODEC_ADPCM)


if __name__ == "__main__":
    unittest.main()
