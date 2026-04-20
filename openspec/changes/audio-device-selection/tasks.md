## 1. Settings Persistence

- [x] 1.1 Add `input_device: null` and `output_device: null` to `_DEFAULTS` in `client/settings.py`

## 2. MicTrack Device Support

- [x] 2.1 Add optional `device: str | None = None` parameter to `MicTrack.__init__`; pass it to `sd.InputStream`
- [x] 2.2 Add `restart_stream(device: str | None)` method to `MicTrack` that stops the current stream and opens a new one with the given device; catch `sd.PortAudioError` / `ValueError` and fall back to `device=None` on failure

## 3. AudioEngine Device Support

- [x] 3.1 Add optional `device: str | None = None` parameter to `AudioEngine.start()`; pass it to `sd.InputStream`
- [x] 3.2 Add optional `device: str | None = None` parameter to `AudioEngine.start_vad()`; forward it to `start()`

## 4. PeerManager / RemoteAudioSink Output Hot-Swap

- [x] 4.1 Replace `self._out_stream` with `self._out_stream_holder: list = [out_stream]` in `PeerManager.__init__`; pass the holder list (not the stream) to `RemoteAudioSink`
- [x] 4.2 Update `RemoteAudioSink.__init__` to accept `out_stream_holder: list` instead of `out_stream: sd.OutputStream`; write via `self._out_stream_holder[0].write(pcm)` in `run()`; catch `Exception` on write (covers stopped-stream errors) and skip the frame
- [x] 4.3 Add `restart_output_stream(device: str | None)` method to `PeerManager` that closes `holder[0]`, opens a new `sd.OutputStream` with the given device (falling back to `None` on error), and assigns it to `holder[0]`; update `close_all()` to close `holder[0]`

## 5. App Integration

- [x] 5.1 In `app.py` `on_mount`: load `input_device` and `output_device` from settings into `self._input_device` and `self._output_device`
- [x] 5.2 Pass `device=self._input_device` to `MicTrack(loop, device=...)` in the vjoin path
- [x] 5.3 Pass `device=self._output_device` to `sd.OutputStream(device=..., ...)` in the vjoin path
- [x] 5.4 Add `_restart_input_device(device: str | None)` method: updates `self._input_device`, saves settings, calls `peer_manager.mic_track.restart_stream(device)` if in voice, re-enters VAD listening if VAD mode active
- [x] 5.5 Add `_restart_output_device(device: str | None)` method: updates `self._output_device`, saves settings, calls `peer_manager.restart_output_stream(device)` if in voice

## 6. MicTestScreen Device Support

- [x] 6.1 In `MicTestScreen.on_mount`, pass `device=getattr(self.app, "_input_device", None)` to `engine.start_vad()`

## 7. DeviceSelectScreen

- [x] 7.1 Create `client/screens/device_select_screen.py` with `DeviceSelectScreen(kind: Literal["input", "output"])` modal; on mount call `sd.query_devices()` and filter by `max_input_channels > 0` or `max_output_channels > 0`; prepend "System Default"; return `None` on cancel, `""` on System Default, device name string on selection

## 8. SettingsScreen Integration

- [x] 8.1 Add `ListItem` with id `item-input-device` and `ListItem` with id `item-output-device` to `SettingsScreen.compose()`; hidden by default when `AUDIO_AVAILABLE` is `False`
- [x] 8.2 Add label helpers `_input_device_label()` and `_output_device_label()` that return `"Input Device: <name or 'System Default'>"` / `"Output Device: <name or 'System Default'>"`
- [x] 8.3 Wire `item-input-device` and `item-output-device` selections in `on_list_view_selected` to open `DeviceSelectScreen` with the appropriate `kind`; on callback call `app._restart_input_device()` / `app._restart_output_device()` and rebuild settings list
- [x] 8.4 Update `_rebuild_settings_list()` and `_all_settings()` to include the device labels and keys

## 9. Tests

- [x] 9.1 Update `tests/test_mic_track.py`: add tests for `device` param passed to `sd.InputStream`; add tests for `restart_stream()` (success, fallback on error)
- [x] 9.2 Update `tests/test_audio_engine.py`: add tests for `device` param in `start()` and `start_vad()`
- [x] 9.3 Update `tests/test_remote_audio_sink.py` (or relevant test): update construction to pass a holder list; verify write goes to `holder[0]`
- [x] 9.4 Create `tests/test_device_select_screen.py`: test device listing, input/output filtering, System Default selection, named device selection, Escape cancellation
- [x] 9.5 Run full test suite and confirm all tests pass
