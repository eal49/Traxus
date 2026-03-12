## 1. Settings and defaults

- [x] 1.1 Add `"vad_custom_threshold": 50.0` to `_DEFAULTS` in `client/settings.py`
- [x] 1.2 Add `"custom"` to `_VAD_SENSITIVITY_CYCLE` in `client/screens/settings_screen.py` (after `"very_high"`)
- [x] 1.3 Add `"Custom"` label to `_VAD_SENSITIVITY_LABELS` in `client/screens/settings_screen.py`
- [x] 1.4 Add a static `ListItem` for `"Custom"` info display in the settings screen compose (label shows threshold value when `"custom"` is selected)

## 2. Settings screen: Custom sensitivity flow

- [x] 2.1 Update `_cycle_vad_sensitivity()` in `SettingsScreen`: when cycling TO `"custom"`, push `VadCalibrationScreen` instead of just saving
- [x] 2.2 Update `_cycle_vad_sensitivity()`: when cycling AWAY from `"custom"`, cycle normally to `"low"`
- [x] 2.3 Update `_rebuild_settings_list()`: when `vad_sensitivity == "custom"`, show threshold value in the label (e.g. `"VAD Sensitivity: Custom (42)"`)
- [x] 2.4 Add `vad_custom_threshold` to `save_settings()` calls in `_cycle_vad_sensitivity()` and `_cycle_ptt_mode()` (preserves the value on mode change)
- [x] 2.5 Add callback `_on_calibration_result(threshold: float | None)` in `SettingsScreen`: on not-None, save `vad_custom_threshold` to settings and update app attribute, then rebuild list

## 3. App-level threshold resolution

- [x] 3.1 Add `_vad_custom_threshold: float` attribute to `TraxusApp.__init__` (loaded from settings, default 50.0)
- [x] 3.2 Add helper `_get_vad_threshold() -> float` in `TraxusApp` that returns `_VAD_SENSITIVITY_THRESHOLDS[_vad_sensitivity]` for named levels or `_vad_custom_threshold` for `"custom"`
- [x] 3.3 Replace direct threshold lookup in `_enter_vad_listening()` with call to `_get_vad_threshold()`
- [x] 3.4 Load `vad_custom_threshold` from settings in `on_mount()` alongside the other settings keys

## 4. VadCalibrationScreen — structure

- [x] 4.1 Create `client/screens/vad_calibration_screen.py` with `VadCalibrationScreen(ModalScreen[float | None])`
- [x] 4.2 `__init__` accepts `initial_threshold: float`; stores it as `_threshold`
- [x] 4.3 `compose()` yields: title label, energy chart `Static` (id=`"energy-chart"`), controls hint label
- [x] 4.4 Define CSS in `VadCalibrationScreen.DEFAULT_CSS`: full-width modal, chart height 26 rows

## 5. VadCalibrationScreen — audio sampling

- [x] 5.1 On `on_mount`: store current app loop; call `app._audio_engine.start_vad(loop, threshold=0, callback=_on_energy)` to open mic stream without VAD firing
- [x] 5.2 `_on_energy(is_voice: bool)` callback is not used for VAD transitions here — instead, hook a separate raw energy callback (add `_energy_callback` to `AudioEngine` alongside the VAD callback, called on every frame with the raw RMS float)
- [x] 5.3 `_on_raw_energy(rms: float)` in the screen: append to a rolling deque of 30 samples; call `self._refresh_chart()` (post via `call_soon_threadsafe`)
- [x] 5.4 On dismiss (both Enter and Escape), call `app._audio_engine.stop_vad()`

## 6. AudioEngine — raw energy callback

- [x] 6.1 Add `_energy_callback: Callable[[float], None] | None = None` to `AudioEngine.__init__`
- [x] 6.2 In `_input_callback`, after computing RMS via `_detect_voice`, if `_energy_callback` is set and `_loop` is set, fire `loop.call_soon_threadsafe(_energy_callback, rms_value)` with the computed RMS
- [x] 6.3 Add `set_energy_callback(cb: Callable[[float], None] | None)` method that sets `_energy_callback`
- [x] 6.4 Clear `_energy_callback` in `stop_vad()`

## 7. VadCalibrationScreen — chart rendering

- [x] 7.1 Implement `_refresh_chart()`: builds a 26-row × 40-col ASCII bar chart from the rolling energy deque
- [x] 7.2 Each row represents an energy band from `MAX_DISPLAY = 500` (top, row 0) to `0` (bottom, row 25); rows at or below the latest RMS sample are filled (`█`), above are empty (` `)
- [x] 7.3 Rows where the band matches the current `_threshold` display a right-aligned marker: `◀ {threshold:.0f}` in yellow Rich markup
- [x] 7.4 Call `self.query_one("#energy-chart", Static).update(chart_text)` to refresh

## 8. VadCalibrationScreen — keyboard handling

- [x] 8.1 Up arrow: `_threshold = min(_threshold + 5, 500)`, refresh chart
- [x] 8.2 Down arrow: `_threshold = max(_threshold - 5, 1)`, refresh chart
- [x] 8.3 Page Up: `_threshold = min(_threshold + 50, 500)`, refresh chart
- [x] 8.4 Page Down: `_threshold = max(_threshold - 50, 1)`, refresh chart
- [x] 8.5 Enter: dismiss with `_threshold`
- [x] 8.6 Escape: dismiss with `None`

## 9. Interval timer for chart refresh

- [x] 9.1 In `on_mount`, start a `set_interval(0.05, _poll_chart)` timer (50ms refresh)
- [x] 9.2 `_poll_chart`: if a new RMS value arrived since last draw, call `_refresh_chart()`; otherwise no-op (avoid redundant redraws)

## 10. Tests

- [x] 10.1 Create `tests/test_vad_calibration.py`
- [x] 10.2 Test `_get_vad_threshold()` returns named-level value for "low", "high", etc.
- [x] 10.3 Test `_get_vad_threshold()` returns `_vad_custom_threshold` when sensitivity is "custom"
- [x] 10.4 Test `AudioEngine.set_energy_callback` sets and clears the callback
- [x] 10.5 Test that `stop_vad()` clears `_energy_callback`
- [x] 10.6 Test `vad_custom_threshold` default is `50.0` in `load_settings()` for a missing file
- [x] 10.7 Test `vad_custom_threshold` round-trips through `save_settings()` / `load_settings()`
- [x] 10.8 Run full test suite; confirm all tests pass
