## Why

Traxus always uses the OS default audio device for both microphone capture and speaker playback. Users with multiple audio devices (USB headsets, multiple monitors with speakers, external microphones) have no way to select the correct device without changing their system default — a disruptive workaround. Device selection should be first-class in the settings screen.

## What Changes

- Add **Input Device** and **Output Device** entries to the Settings screen.
- A new `DeviceSelectScreen` modal enumerates available devices and lets the user pick one (or "System Default").
- Selections are persisted in `settings.json` as `input_device` and `output_device`.
- Device selections take effect **immediately** when changed while in a voice channel — live hot-swap without leaving the channel.
- `MicTrack` gains a `restart_stream(device)` method that swaps the underlying `sd.InputStream` while keeping the aiortc track alive.
- `RemoteAudioSink` and `PeerManager` use a mutable stream holder so the output stream can be swapped without cancelling running sink tasks.
- `AudioEngine` (VAD mode) and `MicTestScreen` respect the selected input device.

## Capabilities

### New Capabilities

- `audio-device-selection`: Settings UI and persistence for user-selected input/output audio devices; live hot-swap of sounddevice streams while in a voice channel.

### Modified Capabilities

- `audio-engine`: `AudioEngine.start()` and `start_vad()` accept an optional `device` parameter.
- `settings-command`: Two new settings items (Input Device, Output Device) added to the Settings screen.

## Impact

- `client/settings.py` — two new default keys
- `client/mic_track.py` — `device` param + `restart_stream()`
- `client/audio_engine.py` — `device` param on `start()` / `start_vad()`
- `client/peer_manager.py` — `_out_stream_holder` list + `restart_output_stream()`
- `client/remote_audio_sink.py` — write via `holder[0]` instead of direct stream reference
- `client/app.py` — load/persist device settings, pass to streams, add restart helpers
- `client/screens/settings_screen.py` — two new list items
- `client/screens/mic_test_screen.py` — pass input device to `start_vad()`
- `client/screens/device_select_screen.py` — new file
- `tests/` — new test file for `DeviceSelectScreen`; updates to `MicTrack`, `AudioEngine`, `PeerManager`, `RemoteAudioSink` tests
