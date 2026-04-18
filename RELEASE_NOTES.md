## What's new

- **Audio jitter buffer** — eliminates voice playback stutter caused by variable
  network inter-packet delay. The playback worker now pre-fills a 100 ms buffer
  (5 frames) before draining at a steady 20 ms clock, so timing variance on the
  wire is absorbed rather than replayed as audible choppiness.
  - Overflow handling switched from drop-oldest to drop-newest, removing the
    waveform discontinuities (clicks/pops) that occurred during bursts.
  - Output stream opened with `latency="low"` to prevent OS-default
    over-buffering on Windows.
  - Underrun timeout raised to 300 ms, preventing false re-prime cycles from
    normal network jitter.
  - Buffer depth is configurable: set `jitter_buffer_frames` in
    `~/.config/traxus/settings.json` (default `5`; reduce to `1` on a LAN).

## Bug fixes

- None.

## Breaking changes

- None.
