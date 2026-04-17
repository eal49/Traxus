## Why

Users have no way to verify their microphone is working or understand what they
actually sound like to others — including how noise suppression changes their
voice. A dedicated mic test screen in settings closes this gap and makes NS a
tangible, audible feature rather than an opaque toggle.

## What Changes

- Add a **Mic Test** entry to the settings menu.
- Add a new `MicTestScreen` modal screen that:
  - Opens the microphone and plays captured audio back through the speakers
    (loopback), so the user hears themselves as others would hear them.
  - Respects the current noise suppression toggle — the loopback reflects NS
    on or off in real time, letting the user hear the difference.
  - Displays a live **spectrogram** (frequency × time ASCII heatmap) so the
    user can see the spectral shape of their voice and the effect of NS.
  - Displays a live **input level bar** (RMS) alongside the spectrogram.
  - Provides a **loopback toggle** (key `L`) so the user can switch hearing
    themselves on/off without leaving the screen.
- `AudioEngine` gains a `loopback_enabled` flag; when set, captured
  (and NS-filtered) PCM is routed directly to the playback queue.

## Capabilities

### New Capabilities

- `mic-test-screen`: Live mic loopback + spectrogram + level bar in a settings
  modal. Lets users hear themselves as others do and see NS in action visually.

### Modified Capabilities

- `audio-engine`: New `loopback_enabled` flag routes filtered capture audio to
  the playback queue; new `set_loopback(enabled)` method.
- `settings-command`: Settings menu gains a "Test Microphone" list item that
  pushes `MicTestScreen`.

## Impact

- New file: `client/screens/mic_test_screen.py`
- Modified: `client/audio_engine.py` — loopback flag + routing in `_input_callback`
- Modified: `client/screens/settings_screen.py` — new menu entry
- New dependency: `numpy` (already required); `numpy.fft` used for spectrogram
  (no new package install needed)
- No server changes, no protocol changes, no settings persistence needed
