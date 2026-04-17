## 1. AudioEngine — loopback support

- [x] 1.1 Add `loopback_enabled: bool = False` attribute to `AudioEngine.__init__`
- [x] 1.2 Add `set_loopback(enabled: bool)` method that sets `loopback_enabled`
- [x] 1.3 In `_input_callback`, after NS processing, if `loopback_enabled` is True put `(CODEC_RAW, pcm_bytes, "")` onto `_play_queue` via `call_soon_threadsafe`
- [x] 1.4 Ensure loopback uses NS-filtered PCM when `noise_suppression_enabled` is True, raw PCM otherwise

## 2. AudioEngine — spectrum callback

- [x] 2.1 Add `_spectrum_callback = None` attribute to `AudioEngine.__init__`
- [x] 2.2 Add `set_spectrum_callback(cb)` method (accepts callable or None)
- [x] 2.3 In `_input_callback`, after NS processing, if `_spectrum_callback` is set, call `loop.call_soon_threadsafe(_spectrum_callback, pcm_bytes)`
- [x] 2.4 Clear `_spectrum_callback` in `stop_vad()` alongside `_energy_callback`

## 3. MicTestScreen — scaffold and layout

- [x] 3.1 Create `client/screens/mic_test_screen.py` with `MicTestScreen(ModalScreen)` class
- [x] 3.2 Add `DEFAULT_CSS` with centered layout, spectrogram widget (width=52, height=18), level bar, status labels
- [x] 3.3 Add `BINDINGS`: `escape → dismiss`, `l → toggle_loopback`
- [x] 3.4 `compose()`: yield title label, spectrogram `Static`, level bar `Static`, NS status label, loopback status label, hint label

## 4. MicTestScreen — spectrogram logic

- [x] 4.1 Add `_spec_history: deque` (maxlen=48) of FFT column lists in `__init__`
- [x] 4.2 Add `_on_spectrum(pcm_bytes)` callback: compute `numpy.fft.rfft` on int16 PCM, take magnitude, bucket into 16 frequency rows, append column to deque
- [x] 4.3 Add `_render_spectrogram()`: iterate history deque left-to-right, build 16-row ASCII grid using `' ░▒▓█'` intensity mapping, return string
- [x] 4.4 Add `_poll()` at 20 Hz (`set_interval(0.05, _poll)`): if new data, update spectrogram and level bar widgets

## 5. MicTestScreen — level bar logic

- [x] 5.1 Add `_rms_history: deque` and `_on_energy(rms)` callback to store latest RMS
- [x] 5.2 Add `_render_level_bar(rms)`: scale RMS to 0–100%, render as filled/empty Unicode bar (40 chars wide) with percentage label

## 6. MicTestScreen — lifecycle (mic open/close, loopback)

- [x] 6.1 `on_mount`: stop any active PTT, then call `engine.start_vad(loop, threshold=0.0, callback=_noop_vad)`, `engine.set_energy_callback(_on_energy)`, `engine.set_spectrum_callback(_on_spectrum)`, `engine.set_loopback(True)`
- [x] 6.2 `on_unmount`: call `engine.set_loopback(False)`, `engine.set_spectrum_callback(None)`, `engine.stop_vad()`
- [x] 6.3 `action_toggle_loopback`: toggle `engine.loopback_enabled`, refresh loopback status label
- [x] 6.4 Display NS status label from `engine.noise_suppression_enabled` on mount

## 7. SettingsScreen — wire Test Microphone entry

- [x] 7.1 Import `AUDIO_AVAILABLE` from `client.audio_engine` in `settings_screen.py`
- [x] 7.2 Add `ListItem(Label("Test Microphone"), id="item-mic-test")` to `compose()`
- [x] 7.3 Add `_update_mic_test_visibility()`: set `display = AUDIO_AVAILABLE` on the item
- [x] 7.4 Call `_update_mic_test_visibility()` in `on_mount` and `_rebuild_settings_list`
- [x] 7.5 In `on_list_view_selected`, handle `item-mic-test`: push `MicTestScreen`

## 8. Tests

- [x] 8.1 Add `TestAudioEngineLoopback` in `tests/test_audio_engine.py`: loopback off by default, set_loopback True/False, loopback puts frame on play_queue, loopback uses NS-filtered bytes when NS on, raw bytes when NS off
- [x] 8.2 Add `TestAudioEngineSpectrumCallback` in `tests/test_audio_engine.py`: callback registered, callback receives pcm bytes, callback cleared on stop_vad, None disables invocation
- [x] 8.3 Add `TestMicTestScreen` in `tests/test_mic_test_screen.py`: screen opens from settings menu, loopback on by default, L key toggles loopback, NS label reflects engine state, unmount disables loopback and stops vad
- [x] 8.4 Add `TestSpectrogramRendering` in `tests/test_mic_test_screen.py`: silence renders spaces, loud signal renders filled chars, column count matches history length
- [x] 8.5 Run full test suite and confirm all tests pass
