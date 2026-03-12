## Why

The four fixed VAD sensitivity levels (Low / Medium / High / Very High) do not accommodate all microphone setups and environments. Users with quiet mics or noisy rooms cannot find a threshold that works for them, leading to either constant false triggers or missed speech detection. A "Custom" level lets users calibrate precisely to their hardware.

## What Changes

- Add a `"custom"` entry to the `_VAD_SENSITIVITY_CYCLE` in the settings screen, following Very High
- Selecting "Custom" in settings opens a `VadCalibrationScreen` modal
- The calibration screen opens the microphone and renders a live spectrogram of incoming audio energy
- A horizontal threshold bar is displayed over the spectrogram; the user moves it up or down with the keyboard to set the desired trigger level
- Accepting (Enter) saves the numeric threshold as `vad_custom_threshold` in settings and closes the screen
- Escape cancels without changing the saved threshold
- When `vad_sensitivity` is `"custom"`, the AudioEngine uses `vad_custom_threshold` instead of a table lookup

## Capabilities

### New Capabilities
- `vad-calibration`: Live spectrogram modal with adjustable threshold bar for custom VAD calibration

### Modified Capabilities
- `settings-command`: Add "Custom" to the VAD Sensitivity cycle; add custom threshold display; add calibration screen launch on selection
- `vad-auto-transmit`: Extend sensitivity resolution to support `"custom"` level reading from `vad_custom_threshold`

## Impact

- `client/screens/settings_screen.py` — add `"custom"` to cycle, show calibration screen on selection
- `client/screens/vad_calibration_screen.py` — new file
- `client/app.py` — `_VAD_SENSITIVITY_THRESHOLDS` extended with `"custom"` key (resolved dynamically from settings)
- `client/settings.py` — `_DEFAULTS` gets `"vad_custom_threshold": 50.0`
- `client/audio_engine.py` — no changes needed (threshold is already passed as a float at `start_vad()` call time)
- `tests/test_vad_calibration.py` — new test file
