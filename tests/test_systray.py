import unittest

from client.systray import _compute_tray_state


class TestComputeTrayState(unittest.TestCase):
    """Unit tests for the pure _compute_tray_state function."""

    def test_disconnected_when_not_connected(self):
        self.assertEqual(
            _compute_tray_state("disconnected", "", False, False, False),
            "disconnected",
        )

    def test_disconnected_when_reconnecting(self):
        self.assertEqual(
            _compute_tray_state("reconnecting", "general", True, True, True),
            "disconnected",
        )

    def test_connected_no_voice(self):
        self.assertEqual(
            _compute_tray_state("connected", "", False, False, False),
            "connected",
        )

    def test_voice_connected_idle(self):
        # In voice channel, not transmitting, VAD not active
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", False, False, False),
            "voice_connected",
        )

    def test_listening_vad_active(self):
        # In voice channel, VAD monitoring below threshold (not transmitting)
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", False, True, False),
            "listening",
        )

    def test_listening_vad_active_with_peers(self):
        # VAD active but not yet transmitting, peers present
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", False, True, True),
            "listening",
        )

    def test_speaking_no_peers(self):
        # Transmitting alone in the channel
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", True, False, False),
            "speaking",
        )

    def test_speaking_and_listening_with_peers(self):
        # Transmitting while others are present
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", True, False, True),
            "speaking_and_listening",
        )

    def test_speaking_and_listening_vad_transmitting_with_peers(self):
        # VAD triggered transmission with peers — transmitting takes precedence over vad_active
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", True, True, True),
            "speaking_and_listening",
        )

    def test_transmitting_takes_precedence_over_vad(self):
        # Once transmitting, vad_active flag does not change the state
        self.assertEqual(
            _compute_tray_state("connected", "voice-1", True, True, False),
            "speaking",
        )

    def test_connection_state_takes_priority_over_all(self):
        # Even if in voice and transmitting, disconnected wins
        self.assertEqual(
            _compute_tray_state("failed", "voice-1", True, True, True),
            "disconnected",
        )


if __name__ == "__main__":
    unittest.main()
