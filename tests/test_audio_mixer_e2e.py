"""
3-client AudioMixer E2E test.

Proves that AudioMixer correctly sums audio from two simultaneous senders:
  - alice sends a 440 Hz tone
  - bob   sends a 880 Hz tone
  - charlie receives and captures the mixed output

The test asserts that charlie's captured PCM contains energy at BOTH
frequencies.  If the mixer were broken (only one sender reaching the
stream, or both silenced), at least one frequency would be absent.

Skipped when aiortc / sounddevice / numpy are not installed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.audio_engine import WEBRTC_AVAILABLE

_REPO_ROOT     = os.path.join(os.path.dirname(__file__), "..")
_CLIENT_SCRIPT = os.path.join(os.path.dirname(__file__), "audio_client.py")
_CHANNEL       = "testvc-mixer-e2e"
_SERVER_PORT   = 8766
_SERVER_URL    = f"ws://localhost:{_SERVER_PORT}"

_ICE_WAIT    = 5.0   # generous: 3 peers → more ICE negotiation
_AUDIO_WAIT  = 3.0
_BUFFER_WAIT = 2.0
_SUBPROCESS_TIMEOUT = 30

# Frequency tolerance: dominant bin must be within this many Hz of target.
_FREQ_TOLERANCE = 80.0


def _has_energy_at(samples, sample_rate: int, target_hz: float, tolerance: float = _FREQ_TOLERANCE) -> tuple[bool, float]:
    """Return (present, peak_hz) — whether the FFT has significant energy near target_hz."""
    import numpy as np
    n = len(samples)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    mag   = np.abs(np.fft.rfft(samples.astype(np.float64)))
    # Find the magnitude at the target frequency ± tolerance
    mask = np.abs(freqs - target_hz) <= tolerance
    if not mask.any():
        return False, 0.0
    local_peak = float(mag[mask].max())
    global_peak = float(mag.max())
    # The target band must account for at least 5 % of total spectral energy
    present = local_peak >= 0.05 * global_peak
    peak_hz = float(freqs[mask][np.argmax(mag[mask])])
    return present, peak_hz


@unittest.skipUnless(WEBRTC_AVAILABLE, "aiortc / sounddevice / numpy not installed")
class TestAudioMixerE2E(unittest.TestCase):
    """3-client pipeline: server + alice (440 Hz) + bob (880 Hz) + charlie (receiver)."""

    @classmethod
    def setUpClass(cls) -> None:
        import os as _os
        env = dict(_os.environ, TRAXUS_PORT=str(_SERVER_PORT))
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "server.main"],
            cwd=_REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._server.terminate()
        try:
            cls._server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls._server.kill()

    def test_mixer_sums_two_senders(self) -> None:
        """
        Charlie must receive energy at BOTH 440 Hz (alice) and 880 Hz (bob).

        This proves AudioMixer is summing frames from both RemoteAudioSinks
        and writing the result to the OutputStream.  If only one sender
        reaches the stream the 880 Hz band (or 440 Hz band) will be absent.
        """
        with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
            output_path = tmp.name

        alice_proc = bob_proc = charlie_proc = None
        try:
            common = [
                sys.executable, _CLIENT_SCRIPT,
                "--channel",    _CHANNEL,
                "--server",     _SERVER_URL,
                "--ice-wait",   str(_ICE_WAIT),
                "--audio-wait", str(_AUDIO_WAIT),
            ]

            alice_proc = subprocess.Popen(
                common + ["--role", "sender", "--username", "alice", "--freq", "440"],
                cwd=_REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            bob_proc = subprocess.Popen(
                common + ["--role", "sender", "--username", "bob", "--freq", "880"],
                cwd=_REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            charlie_proc = subprocess.Popen(
                common + [
                    "--role",        "receiver",
                    "--username",    "charlie",
                    "--output",      output_path,
                    "--buffer-wait", str(_BUFFER_WAIT),
                ],
                cwd=_REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

            # Drain all three pipes simultaneously in background threads.
            # Sequential communicate() calls would starve non-active processes:
            # verbose aioice logs can fill a pipe buffer while only one pipe is
            # being read, blocking the subprocess on its next log write and
            # preventing it from sending SDP answers → WebRTC stalls → silence.
            stderr_output: dict[str, bytes] = {}
            timed_out: list[str] = []

            def _communicate(proc, role):
                try:
                    _, stderr_bytes = proc.communicate(timeout=_SUBPROCESS_TIMEOUT)
                    stderr_output[role] = stderr_bytes
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    timed_out.append(role)

            drain_threads = [
                threading.Thread(target=_communicate, args=(proc, role), daemon=True)
                for role, proc in [("alice", alice_proc), ("bob", bob_proc), ("charlie", charlie_proc)]
            ]
            for t in drain_threads:
                t.start()
            for t in drain_threads:
                t.join(timeout=_SUBPROCESS_TIMEOUT + 10)

            if timed_out:
                for p in [alice_proc, bob_proc, charlie_proc]:
                    if p and p.poll() is None:
                        p.kill()
                self.fail(f"{timed_out[0]} subprocess timed out after {_SUBPROCESS_TIMEOUT}s")

            for role, proc in [("alice", alice_proc), ("bob", bob_proc), ("charlie", charlie_proc)]:
                if proc.returncode != 0:
                    self.fail(
                        f"{role} exited with code {proc.returncode}.\n"
                        f"stderr: {stderr_output.get(role, b'').decode(errors='replace')}"
                    )

            self.assertTrue(os.path.exists(output_path), "charlie produced no output file")
            self.assertGreater(os.path.getsize(output_path), 0, "charlie output file is empty")

            import numpy as np
            with open(output_path, "rb") as f:
                raw = f.read()
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)

            rms = float(np.sqrt(np.mean(samples ** 2)))
            self.assertGreater(rms, 200.0, f"Overall RMS={rms:.1f} too low — audio may be silent")

            recv_sr = 48_000  # aiortc always decodes Opus at 48 kHz

            has_440, peak_440 = _has_energy_at(samples, recv_sr, 440.0)
            has_880, peak_880 = _has_energy_at(samples, recv_sr, 880.0)

            self.assertTrue(
                has_440,
                f"No 440 Hz energy in charlie's output (peak near 440 Hz: {peak_440:.1f} Hz). "
                "Alice's audio did not reach the mixer.",
            )
            self.assertTrue(
                has_880,
                f"No 880 Hz energy in charlie's output (peak near 880 Hz: {peak_880:.1f} Hz). "
                "Bob's audio did not reach the mixer — mixing may be broken.",
            )

        finally:
            for proc in [alice_proc, bob_proc, charlie_proc]:
                if proc is not None and proc.poll() is None:
                    proc.kill()
            try:
                os.unlink(output_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
