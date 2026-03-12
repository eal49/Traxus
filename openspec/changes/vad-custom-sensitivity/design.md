## Context

Traxus already has four fixed VAD sensitivity levels (Low, Medium, High, Very High) stored as static RMS energy thresholds in `_VAD_SENSITIVITY_THRESHOLDS`. The settings screen cycles through them; the selected level is resolved to a float and passed to `AudioEngine.start_vad()` at activation time.

The feature adds a fifth option — "Custom" — that skips the lookup table and lets the user pick an exact threshold via a live audio calibration screen. The calibration screen must:

1. Open the microphone immediately (or reuse the already-open VAD stream)
2. Visualize incoming audio energy in real time
3. Let the user move a threshold bar up/down to the desired level
4. Save the chosen value on confirmation

Textual 8 has no built-in chart or canvas widget. Energy visualization must be done with Rich markup rendered through a `Static` widget refreshed on a timer.

## Goals / Non-Goals

**Goals:**
- Add "Custom" to the sensitivity cycle (after Very High → wraps back to Low)
- New `VadCalibrationScreen` modal: live ASCII bar chart of microphone energy with a movable threshold line
- Keyboard-driven threshold adjustment (Up/Down arrows, PgUp/PgDn for coarse steps)
- On confirmation, save `vad_custom_threshold: float` to settings
- When `vad_sensitivity == "custom"`, AudioEngine uses the saved float directly
- Default `vad_custom_threshold` is `50.0` (same as the "high" preset)

**Non-Goals:**
- Mouse drag on the threshold bar (terminal mouse events are unreliable for drag)
- FFT/frequency-domain spectrogram (RMS energy bar chart is sufficient for threshold calibration)
- Waveform display (energy level is what matters for VAD tuning)
- Changing the visualization update rate to sub-20ms (20ms matches audio block size)

## Decisions

### D1: Visualization approach — ASCII bar chart via Rich markup

**Decision:** Render a vertical ASCII bar chart (each row = one energy band, rightmost column = threshold marker) using Rich `Text` markup inside a `Static` widget. Refresh on a 50ms `set_interval` timer.

**Alternatives considered:**
- Textual `Sparkline` widget: only available in newer Textual versions, not confirmed in 8.0.2
- Raw `RichLog` append: creates unbounded scroll history; not suitable for live display
- External plotting library (plotext): adds a runtime dependency for a single screen

**Rationale:** Zero new dependencies. `Static.update()` is sync-safe from a timer callback. A rolling buffer of ~20 energy samples gives a clear visual of recent mic activity.

### D2: Mic stream lifecycle during calibration

**Decision:** `VadCalibrationScreen` calls `app._audio_engine.start_vad(loop, threshold=0, callback=_calibration_callback)` on mount (making the stream idempotent if VAD is already active) and `app._audio_engine.stop_vad()` on dismiss — unless the app is currently in active VAD listening mode, in which case calibration re-uses the live stream and restores it on dismiss.

**Simpler alternative:** Always stop and restart the stream. This causes a brief audio gap but is much simpler.

**Decision taken:** Always stop on enter calibration, restart on exit with the new threshold. The user is in a settings modal — audio transmission is not expected. This avoids needing to track stream ownership.

### D3: Threshold bar representation

**Decision:** The bar chart is a fixed-height display (24 rows). Each row represents an energy level from 0 (bottom) to `MAX_DISPLAY_ENERGY = 500` (top). Incoming RMS values are plotted as a bar from the bottom. The threshold row is highlighted with a distinct marker (`◀ threshold`). Up/Down arrows move the threshold by 5 units; PgUp/PgDn by 50 units.

**Rationale:** Fixed scale makes it easy to compare energy levels across sessions. 500 is safely above the "low" preset (200) and well above typical speech RMS for int16.

### D4: Settings persistence

**Decision:** `vad_custom_threshold` is a new key in `settings.json` with default `50.0`. It is always saved alongside the other settings keys. When `vad_sensitivity != "custom"` it is ignored but still persisted.

**Alternative:** Only write `vad_custom_threshold` when "custom" is selected. Simpler, but causes the value to disappear on round-trips through other modes.

### D5: Threshold resolution in app.py

**Decision:** `_VAD_SENSITIVITY_THRESHOLDS` gains a sentinel value `"custom": 0.0`. In `_enter_vad_listening()`, after looking up the threshold, if the result is `0.0` AND `_vad_sensitivity == "custom"`, the app reads `vad_custom_threshold` from `load_settings()`.

**Simpler alternative:** Add a helper `_get_vad_threshold() -> float` that branches on the sensitivity string. This is cleaner and avoids the sentinel pattern.

**Decision taken:** Use the helper function. Sentinel values are error-prone.

## Risks / Trade-offs

- [Terminal refresh rate] 50ms timer × Static.update() may flicker on slow terminals → Mitigation: use full-block redraw (replace entire content) rather than incremental updates; Textual batches redraws efficiently
- [Mic permissions on first calibration open] Some systems show a permission dialog on first mic access → No mitigation needed; this is the same as PTT activation
- [Audio thread contention] Calibration screen sets a callback on the AudioEngine while VAD mode may already have one → Mitigation: `start_vad()` replaces the callback atomically; `stop_vad()` clears it

## Migration Plan

No data migration needed. `vad_custom_threshold` is added to `_DEFAULTS`; existing settings files without it will read the default on load.

## Open Questions

- None blocking implementation.
