## What's new

- **Spectral noise suppression** — background noise is filtered from your microphone
  signal before transmission using a spectral subtraction algorithm.
- **Noise suppression toggle** — enable or disable noise suppression at runtime via
  the settings menu (`/settings`). The preference is persisted to `settings.json`.
- **Per-participant volume control** — adjust the playback volume of each voice
  participant (0–200%) directly in the Members panel. Use arrow keys when the panel
  is focused: ↑/↓ to select a participant, ←/→ to decrease/increase their volume by
  10%. The bar updates in real time.

## Bug fixes

- Fixed missing error message when the initial server connection attempt fails.

## Breaking changes

- None.
