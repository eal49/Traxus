### Requirement: Spectral noise suppression on captured audio
When noise suppression is available (`NS_AVAILABLE` is `True`), the AudioEngine SHALL apply a `_SpectralNoiseSuppressor` filter to each captured PCM frame before ADPCM encoding (or raw queuing if ADPCM is unavailable). When noise suppression is unavailable, the AudioEngine SHALL skip the filter step silently and process the raw PCM frame as usual.

`NS_AVAILABLE` is set at import time based on whether `numpy` and `scipy` (or an equivalent FFT provider) are importable.

#### Scenario: Noise suppressor is applied before ADPCM encode
- **WHEN** `NS_AVAILABLE` is `True` and PTT is active and a PCM block arrives in the sounddevice callback
- **THEN** the block SHALL be passed through `_SpectralNoiseSuppressor.process(pcm)` before being encoded via `shared/adpcm.encode()`

#### Scenario: Noise suppressor is applied before raw PCM queuing
- **WHEN** `NS_AVAILABLE` is `True` and numpy is not importable (ADPCM unavailable) and PTT is active
- **THEN** the block SHALL be passed through `_SpectralNoiseSuppressor.process(pcm)` before being placed on the capture queue as raw PCM

#### Scenario: Graceful degradation when NS unavailable
- **WHEN** `NS_AVAILABLE` is `False` (numpy/scipy not importable) and PTT is active
- **THEN** the AudioEngine SHALL process the PCM frame without any noise suppression filter
- **THEN** no exception is raised and transmission continues normally

#### Scenario: NS_AVAILABLE flag is set at import time
- **WHEN** the `audio_engine` module is imported
- **THEN** `NS_AVAILABLE` SHALL be `True` if and only if numpy and scipy (or equivalent) are importable
- **THEN** `NS_AVAILABLE` SHALL be `False` if either dependency is missing

---

### Requirement: _SpectralNoiseSuppressor interface
The `_SpectralNoiseSuppressor` class SHALL expose a single `process(pcm_bytes: bytes) -> bytes` method that accepts a raw PCM frame (int16, mono, 16 kHz) and returns a noise-suppressed PCM frame of identical length.

#### Scenario: Output length matches input
- **WHEN** `_SpectralNoiseSuppressor.process()` is called with a 640-byte PCM frame (320 samples × 2 bytes)
- **THEN** the returned bytes object SHALL also be 640 bytes

#### Scenario: Suppressor reduces constant background noise
- **WHEN** the input frame contains a known stationary noise signal
- **THEN** the output frame's RMS energy SHALL be lower than the input frame's RMS energy
