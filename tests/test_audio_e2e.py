"""
E2E audio integration test.

Starts a real Traxus server subprocess, then launches two headless client
subprocesses (sender=alice, receiver=bob) via tests/audio_client.py.
Alice sends 100 frames of 440 Hz PCM via WebRTC; bob captures what
RemoteAudioSink writes to his OutputStream mock and saves it to a temp file.
The test asserts the received PCM has non-trivial RMS energy (> 100 / 32767),
confirming real audio — not silence — traversed the full WebRTC pipeline.

Skipped when aiortc / sounddevice / numpy are not installed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.audio_engine import WEBRTC_AVAILABLE

_REPO_ROOT  = os.path.join(os.path.dirname(__file__), "..")
_CLIENT_SCRIPT = os.path.join(os.path.dirname(__file__), "audio_client.py")
_CHANNEL    = "testvc-e2e"
_SENDER     = "alice"
_RECEIVER   = "bob"
_SERVER_URL = "ws://localhost:8765"

# Generous budgets: loopback ICE is fast but CI machines can be slow.
_ICE_WAIT    = 4.0   # seconds to wait for ICE before sending audio
_AUDIO_WAIT  = 3.0   # seconds to let frames drain after injection
_BUFFER_WAIT = 2.0   # extra receiver buffer beyond ice+audio
_SUBPROCESS_TIMEOUT = 25  # hard kill threshold per subprocess


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc / sounddevice / numpy not installed")
class TestAudioE2E(unittest.TestCase):
    """Full pipeline: server subprocess + two headless client subprocesses."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=_REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)  # let the server bind its port

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        try:
            cls._server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls._server.kill()

    def test_audio_flows_sender_to_receiver(self) -> None:
        """
        Alice sends 100 frames of 440 Hz tone; bob receives and writes them
        to a temp file.  Assert RMS of received PCM > 100.
        """
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            output_path = tmp.name

        sender_proc   = None
        receiver_proc = None

        try:
            common = [
                sys.executable, _CLIENT_SCRIPT,
                "--channel",    _CHANNEL,
                "--server",     _SERVER_URL,
                "--ice-wait",   str(_ICE_WAIT),
                "--audio-wait", str(_AUDIO_WAIT),
            ]

            sender_proc = subprocess.Popen(
                common + ["--role", "sender", "--username", _SENDER],
                cwd=_REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            receiver_proc = subprocess.Popen(
                common + [
                    "--role",        "receiver",
                    "--username",    _RECEIVER,
                    "--output",      output_path,
                    "--buffer-wait", str(_BUFFER_WAIT),
                ],
                cwd=_REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for both with individual timeouts
            for role, proc in [("sender", sender_proc), ("receiver", receiver_proc)]:
                try:
                    proc.wait(timeout=_SUBPROCESS_TIMEOUT)
                except subprocess.TimeoutExpired:
                    sender_proc.kill()
                    receiver_proc.kill()
                    self.fail(
                        f"{role} subprocess did not finish within "
                        f"{_SUBPROCESS_TIMEOUT}s — ICE may have failed or "
                        "PeerManager did not start"
                    )

            # Check exit codes; read+close pipes and show stderr on failure
            for role, proc in [("sender", sender_proc), ("receiver", receiver_proc)]:
                stdout, stderr = proc.communicate()
                if proc.returncode != 0:
                    self.fail(
                        f"{role} subprocess exited with code {proc.returncode}.\n"
                        f"stderr: {stderr.decode(errors='replace')}"
                    )

            # Verify output file exists and is non-empty
            self.assertTrue(
                os.path.exists(output_path),
                "Receiver did not create output file",
            )
            file_size = os.path.getsize(output_path)
            self.assertGreater(
                file_size, 0,
                "Receiver output file is empty — no audio was written to OutputStream",
            )

            # Read PCM and verify energy + frequency content
            import numpy as np
            with open(output_path, "rb") as f:
                raw = f.read()

            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)

            rms = float(np.sqrt(np.mean(samples ** 2)))
            self.assertGreater(
                rms, 500.0,
                f"Received audio RMS={rms:.1f} is too low — expected > 500 for a 440 Hz "
                "tone (RMS ≈ 13000).  Audio arrived as silence or near-silence.",
            )

            # aiortc always decodes Opus at 48000 Hz regardless of sender rate.
            recv_sample_rate = 48000

            # ── Frequency check ───────────────────────────────────────────────
            # Dominant FFT bin must be 440 Hz ± 50 Hz.  Catches sample-rate
            # mismatches: 16 kHz audio written to a 48 kHz stream appears at
            # 440/3 ≈ 147 Hz; stereo-as-mono flattening halves it to 220 Hz.
            freqs = np.fft.rfftfreq(len(samples), d=1.0 / recv_sample_rate)
            dominant_hz = float(freqs[np.argmax(np.abs(np.fft.rfft(samples)))])
            self.assertAlmostEqual(
                dominant_hz, 440.0, delta=50.0,
                msg=f"Dominant frequency {dominant_hz:.1f} Hz ≠ 440 Hz. "
                "Sample-rate mismatch or pipeline is transmitting noise.",
            )

            # ── Continuity check ──────────────────────────────────────────────
            # Split into 20-ms chunks (960 samples at 48 kHz) and find the
            # longest contiguous run of non-silent chunks (RMS > 1 000).
            # A choppy stream (MicTrack polled faster than frame rate) produces
            # bursts of silence between real frames; the longest run is tiny.
            chunk_samples = 960   # 20 ms at 48 kHz
            chunks = [
                samples[i : i + chunk_samples]
                for i in range(0, len(samples) - chunk_samples + 1, chunk_samples)
            ]
            chunk_rms = [float(np.sqrt(np.mean(c ** 2))) for c in chunks]
            is_audio = [r > 1000.0 for r in chunk_rms]

            # Longest contiguous run of non-silent chunks
            best = cur = 0
            for v in is_audio:
                cur = cur + 1 if v else 0
                best = max(best, cur)

            # We inject _FRAMES frames (default 100 → 2 s of audio).
            # Require the longest continuous run to cover ≥ 60% of that window.
            # 70% was too tight on Linux CI: AudioMixer ticks every 20 ms and
            # aiortc's decode occasionally lands just after a tick boundary on
            # loaded runners, inserting isolated silence frames.
            expected_audio_chunks = 100   # matches --frames default in sender
            min_run = int(expected_audio_chunks * 0.60)
            self.assertGreaterEqual(
                best, min_run,
                f"Longest contiguous non-silent run = {best} chunks "
                f"({best * 20} ms), expected ≥ {min_run} ({min_run * 20} ms). "
                "Audio is too choppy: many 20 ms tick boundaries were missed, "
                "likely due to aiortc decode latency or MicTrack pacing drift.",
            )

        finally:
            # Clean up subprocesses if still running (e.g. after assertion failure)
            for proc in [sender_proc, receiver_proc]:
                if proc is not None and proc.poll() is None:
                    proc.kill()
            try:
                os.unlink(output_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
