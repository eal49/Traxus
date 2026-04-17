## Context

The settings menu already has a `VadCalibrationScreen` that opens the mic,
shows a live RMS bar chart, and uses `_energy_callback` to receive energy
samples. The `AudioEngine` already runs spectral NS on every captured frame
(even while idle) and exposes `_play_queue` for playback. `numpy.fft` is
available as a transitive dependency of numpy (already required).

The goal is a mic test screen that reuses these hooks but adds loopback audio
and a spectrogram — giving users a richer experience than calibration.

## Goals / Non-Goals

**Goals:**
- Loopback: route NS-filtered (or raw) PCM to `_play_queue` so the user hears
  themselves exactly as others do.
- Live spectrogram: ASCII frequency × time heatmap built from `numpy.fft.rfft`
  on each incoming frame.
- Live RMS level bar alongside the spectrogram.
- Loopback toggle (`L`) without leaving the screen.
- Visible NS state (on/off label); changing NS in settings is out of scope for
  this screen but the loopback reflects whatever NS is currently set to.
- Entry point: new "Test Microphone" item in `SettingsScreen`.

**Non-Goals:**
- In-screen NS toggle (user goes to settings for that).
- Saving any state or preferences from this screen.
- Waveform oscilloscope view (spectrogram covers the interesting information).
- Audio recording or export.

## Decisions

### D1 — Loopback via `loopback_enabled` flag on `AudioEngine`

`_input_callback` already computes `pcm_filtered` (or falls back to raw) on
every frame. Adding a `loopback_enabled: bool` flag means the loopback path
is a single `_play_queue.put_nowait((CODEC_RAW, pcm_bytes, ""))` in the audio
thread, with no new thread or stream needed. The playback worker already runs
whenever the engine is started.

Alternative considered: a separate `sd.OutputStream` inside `MicTestScreen`.
Rejected — duplicate stream management, potential device conflicts.

### D2 — Spectrogram as ASCII heatmap, not a waveform

The VAD calibration screen already does a time-domain energy bar. A frequency
× time heatmap (spectrogram) is orthogonally different: each column is one FFT
frame, each row is a frequency bucket, intensity is encoded in Unicode block
characters (`░▒▓█`). This makes NS visually obvious — noise fills the spectrum
flatly; NS carves it out.

Layout (width=48 chars, height=16 rows):

```
  High │░░░░░░░░░░░░▒▒▓▓▓▓▒▒░░░░░░░░░░░░░░░░░░░░░░░░░
       │░░░░░░░░░░▒▒▓▓██▓▓▒▒░░░░░░░░░░░░░░░░░░░░░░░░░
  ...  │ ...
   Low │░░░░░░░░░░░░░░░░░░▒▒░░░░░░░░░░░░░░░░░░░░░░░░░
         oldest ─────────────────────────────── newest
```

Each new FFT frame shifts the display one column to the left (rolling buffer).
Intensity thresholds map magnitude to character:
`0–10% → ' '`, `10–30% → '░'`, `30–60% → '▒'`, `60–85% → '▓'`, `85–100% → '█'`.

### D3 — Spectrogram data flows via `_spectrum_callback`, parallel to `_energy_callback`

`AudioEngine` gets a `set_spectrum_callback(cb)` analogous to `set_energy_callback`.
The callback receives the raw `pcm_filtered` (or raw PCM) as `bytes`, and
`MicTestScreen` does the FFT on the asyncio loop (not in the audio thread) to
keep the callback fast. FFT on 320 samples takes ~10 µs — negligible.

Alternative: do FFT inside `_input_callback` (audio thread). Rejected — audio
callbacks must return quickly; numpy FFT is fast but adds jitter.

### D4 — `MicTestScreen` reuses `start_vad` / `stop_vad` to open the mic

`start_vad` is the existing "open mic for monitoring" API. `MicTestScreen` calls
it with `threshold=0.0` and a no-op VAD callback (same as `VadCalibrationScreen`).
This avoids duplicating stream lifecycle code.

### D5 — Refresh rate: 20 Hz (`set_interval(0.05, ...)`)

Same as `VadCalibrationScreen`. Each tick drains any pending samples from the
rolling deques and redraws. At 50 fps input, up to ~2–3 frames may buffer
between ticks — harmless for a visual display.

## Risks / Trade-offs

- **Loopback latency**: audio thread → `call_soon_threadsafe` → event loop →
  `_play_queue` → playback worker → OutputStream. Typically 50–150 ms.
  Noticeable echo but acceptable for "hear what you sound like" — not a
  real-time monitoring tool. Mitigation: label it "slight delay is normal."
- **Device conflicts**: if the user's device can't open input and output
  simultaneously, loopback will silently fail. The existing playback worker is
  already started by the app; only the mic stream is new here. Low risk on
  typical hardware.
- **`_spectrum_callback` added to `AudioEngine`**: this grows the callback
  surface. It's gated by `if self._spectrum_callback is not None` so no cost
  when unused. Risk: none.

## Open Questions

- None — scope is fully defined.
