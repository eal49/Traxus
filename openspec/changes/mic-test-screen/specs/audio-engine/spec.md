## ADDED Requirements

### Requirement: AudioEngine supports loopback mode
`AudioEngine` SHALL expose a `loopback_enabled: bool` attribute (default `False`)
and a `set_loopback(enabled: bool)` method. When `loopback_enabled` is `True`,
the `_input_callback` SHALL route the NS-filtered (or raw, if NS is off) PCM
bytes directly to `_play_queue` as a `(CODEC_RAW, pcm_bytes, "")` tuple, in
addition to any normal capture path behaviour.

#### Scenario: Loopback routes filtered audio to playback
- **WHEN** `loopback_enabled` is `True` and `noise_suppression_enabled` is `True`
- **THEN** each captured frame SHALL be placed onto `_play_queue` as raw PCM after NS filtering

#### Scenario: Loopback routes raw audio when NS disabled
- **WHEN** `loopback_enabled` is `True` and `noise_suppression_enabled` is `False`
- **THEN** each captured frame SHALL be placed onto `_play_queue` as raw captured PCM

#### Scenario: No loopback when flag is False
- **WHEN** `loopback_enabled` is `False`
- **THEN** captured frames SHALL NOT be placed onto `_play_queue` by the capture path

#### Scenario: set_loopback enables loopback
- **WHEN** `set_loopback(True)` is called
- **THEN** `loopback_enabled` SHALL be `True`

#### Scenario: set_loopback disables loopback
- **WHEN** `set_loopback(False)` is called
- **THEN** `loopback_enabled` SHALL be `False`

---

### Requirement: AudioEngine supports a spectrum callback
`AudioEngine` SHALL expose a `set_spectrum_callback(cb)` method. When set, `cb`
SHALL be called on the asyncio event loop (via `call_soon_threadsafe`) once per
captured frame, receiving the NS-filtered (or raw) PCM as `bytes`. The callback
SHALL only be invoked when the mic stream is open. Setting the callback to `None`
SHALL disable it.

#### Scenario: Spectrum callback receives PCM bytes each frame
- **WHEN** `set_spectrum_callback(cb)` has been called and the mic stream is open
- **THEN** `cb` SHALL be invoked on every captured frame with the PCM bytes as its sole argument

#### Scenario: Spectrum callback receives NS-filtered bytes when NS is on
- **WHEN** `noise_suppression_enabled` is `True` and the spectrum callback is set
- **THEN** the bytes passed to the callback SHALL be the NS-filtered PCM

#### Scenario: No spectrum callback invocation when not set
- **WHEN** `set_spectrum_callback(None)` has been called
- **THEN** the audio thread SHALL NOT attempt to invoke a spectrum callback
