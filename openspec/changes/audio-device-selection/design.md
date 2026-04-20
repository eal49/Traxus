## Context

Traxus uses sounddevice for microphone capture (`MicTrack`, `AudioEngine`) and speaker playback (`sd.OutputStream` in `app.py`). All three stream constructors currently omit the `device=` parameter, relying on the OS default. There are three independent stream lifetimes to manage:

1. **MicTrack** — `sd.InputStream`, opened on `/vjoin`, owned by `PeerManager`
2. **AudioEngine** — `sd.InputStream`, opened on VAD start or `MicTestScreen` launch
3. **OutputStream** — `sd.OutputStream`, opened on `/vjoin`, owned by `PeerManager`; written to by N concurrent `RemoteAudioSink` asyncio tasks

## Goals / Non-Goals

**Goals:**
- Allow users to select input and output devices independently from the Settings screen
- Persist selections across restarts in `settings.json`
- Hot-swap devices while in a voice channel without leaving/rejoining
- `MicTestScreen` opens the mic on the selected input device
- Graceful fallback to OS default when a saved device is no longer available

**Non-Goals:**
- Per-channel device profiles
- Automatic device switching when a preferred device is plugged in
- Displaying device sample rates, latency, or channel counts in the picker
- Support for exclusive-mode / WASAPI/ASIO device configuration

## Decisions

### D1: MicTrack hot-swap via stream replacement (not track replacement)

aiortc sees `MicTrack` as a track that exposes a `recv()` coroutine pulling from an internal `asyncio.Queue`. The sounddevice stream only *feeds* that queue — it is invisible to aiortc. Swapping the underlying `sd.InputStream` (stop old, open new with new device) leaves the queue and the aiortc track untouched. No WebRTC renegotiation is needed.

Alternative considered: `RTCRtpSender.replaceTrack()`. aiortc does not expose this API, and even if it did, swapping the stream is simpler and avoids any signalling round-trip.

### D2: OutputStream hot-swap via mutable holder list

`RemoteAudioSink` tasks run tight `while True` loops writing `self._out_stream.write(pcm)`. If we give them a direct reference to the stream, we cannot swap it without cancelling all tasks (which would cause an audio gap of 1–2 s while tasks restart and re-receive track events).

Instead, `PeerManager` holds `self._out_stream_holder: list[sd.OutputStream] = [stream]`. `RemoteAudioSink` receives this list and writes `self._out_stream_holder[0].write(pcm)`. To hot-swap:

```
holder[0].stop(); holder[0].close()
holder[0] = new_stream   # atomic list item assignment
new_stream.start()
```

Running sink tasks see the new stream on their very next frame. Zero gap, no task restarts.

Alternative considered: cancel + restart sink tasks. Works but introduces a gap and requires tracking track references separately.

### D3: AudioEngine device param threaded through start() / start_vad()

`AudioEngine.start()` and `start_vad()` accept an optional `device: str | None` parameter (default `None` = system default). `MicTestScreen` reads `getattr(self.app, "_input_device", None)` and passes it through. No global state on `AudioEngine` — callers supply the device at open time.

### D4: Device stored as name string, not integer index

sounddevice device indices shift when USB devices are plugged/unplugged. Storing the device *name* (string) is more stable. sounddevice accepts a name string in `device=` and matches by prefix. On stream open, if the named device is not found, we catch the `sd.PortAudioError` / `ValueError` and fall back to the system default, printing a warning to the chat screen.

### D5: DeviceSelectScreen is a reusable parameterised modal

One screen, `DeviceSelectScreen(kind: Literal["input", "output"])`, used for both input and output selection. It calls `sd.query_devices()` at mount time, filters by `max_input_channels > 0` or `max_output_channels > 0`, and presents a `ListView` with "System Default" prepended.

Return value convention (mirrors `PttKeyScreen`):
- `None` — user cancelled (no change)
- `""` — user selected System Default
- `"device name"` — user selected a specific device

### D6: Changes take effect immediately when in a voice channel

When the user confirms a new input device:
1. `app._input_device` is updated and persisted
2. If `app._peer_manager` is not None: `peer_manager.mic_track.restart_stream(new_device)`
3. If VAD mode is active: `app._exit_vad_listening(); app._enter_vad_listening()` (re-opens AudioEngine stream)

When the user confirms a new output device:
1. `app._output_device` is updated and persisted
2. If `app._peer_manager` is not None: `peer_manager.restart_output_stream(new_device)`

## Risks / Trade-offs

- **Device not found at stream open** — sounddevice raises if the named device doesn't exist or doesn't support the requested sample rate. Mitigation: catch the exception, fall back to `device=None`, show a warning in the chat area.
- **Race condition during swap** — a `RemoteAudioSink` frame write could occur between `holder[0].stop()` and `holder[0] = new_stream`. Mitigation: sounddevice `write()` on a stopped stream raises; catch `sd.PortAudioError` in `RemoteAudioSink.run()` and skip the write (one dropped frame, not a crash).
- **MicTrack stream restart drops in-flight queue frames** — stopping the old stream empties `_queue` indirectly (no new frames are enqueued). In-flight frames already in the queue drain normally. Acceptable: <20 ms gap.
- **VAD mode restart** — calling `_exit_vad_listening` / `_enter_vad_listening` while transmitting could briefly stop PTT. Mitigation: device change during active transmission is an edge case; the brief gap is acceptable.

## Migration Plan

No server changes. No migration needed. New `settings.json` keys default to `null` (system default), so existing configs continue to work unchanged.
