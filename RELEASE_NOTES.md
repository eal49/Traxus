## What's new

- **Audio jitter buffer** — eliminates voice playback stutter caused by variable
  network inter-packet delay. The playback worker now pre-fills a small buffer
  (default 60 ms = 3 frames) before draining at a steady 20 ms clock, so timing
  variance on the wire is absorbed rather than replayed as audible choppiness.
  - Overflow handling switched from drop-oldest to drop-newest, removing the
    waveform discontinuities (clicks/pops) that occurred during bursts.
  - Output stream opened with `latency="low"` to prevent OS-default
    over-buffering on Windows.
  - Buffer depth is configurable: set `jitter_buffer_frames` in
    `~/.config/traxus/settings.json` (default `3`; reduce to `1` on a LAN,
    increase to `5`+ on a high-latency connection).

## Bug fixes

- None.

## Breaking changes

- None.
