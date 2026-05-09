## Why

When 3 or more clients join the same voice channel, each `RemoteAudioSink` concurrently calls `sd.OutputStream.write()` on a single shared stream from separate executor threads. PortAudio serializes those writes rather than mixing them, so participants hear each other in choppy round-robin instead of simultaneously — audio is unintelligible or silent depending on buffer state.

## What Changes

- Introduce a new `AudioMixer` component that owns the `sd.OutputStream` and is the sole writer to it.
- `RemoteAudioSink` no longer writes to the stream directly; it enqueues decoded PCM into a per-user slot in the mixer.
- A single mixer task wakes every 20 ms, sums all queued frames as float32 (clips to int16), and performs one write per frame period regardless of how many speakers are active.
- `PeerManager` creates and owns one `AudioMixer` per voice session; it adds/removes user slots on connect/disconnect.
- Output device hot-swap (`restart_output_stream`) moves from `PeerManager` to `AudioMixer`.
- Per-user volume gain remains in `RemoteAudioSink` (applied before enqueue, unchanged behaviour).

## Capabilities

### New Capabilities
- `audio-mixer`: Single-writer software mixer that sums PCM from N concurrent remote speakers into one `sd.OutputStream` write per 20 ms frame.

### Modified Capabilities
- `webrtc-audio-transport`: The playback path through `RemoteAudioSink` and `PeerManager` changes — sinks now push to a mixer queue instead of writing directly to the output stream.

## Impact

- **New file**: `client/audio_mixer.py`
- **Modified**: `client/remote_audio_sink.py`, `client/peer_manager.py`, `client/app.py`
- **New tests**: `tests/test_audio_mixer.py`
- **Existing tests**: all must remain green; `test_remote_audio_sink.py`, `test_peer_manager.py` may need sink/mixer wiring updates
- **No API or protocol changes** — purely internal playback path
