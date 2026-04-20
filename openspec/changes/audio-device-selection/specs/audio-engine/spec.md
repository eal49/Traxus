## MODIFIED Requirements

### Requirement: AudioEngine start() is idempotent
Calling `AudioEngine.start(loop, device=None)` when the stream is already open SHALL be a no-op. The method SHALL accept an optional `device` parameter (string device name or `None` for system default) which is passed to `sd.InputStream` at stream open time.

#### Scenario: Double start does not crash
- **WHEN** `AudioEngine.start()` is called while the stream is already open
- **THEN** no exception is raised and the existing stream remains open

#### Scenario: start() passes device to sd.InputStream
- **WHEN** `AudioEngine.start(loop, device="Blue Yeti")` is called
- **THEN** `sd.InputStream` SHALL be opened with `device="Blue Yeti"`

#### Scenario: start() uses system default when device is None
- **WHEN** `AudioEngine.start(loop, device=None)` is called
- **THEN** `sd.InputStream` SHALL be opened without a `device=` argument

---

## ADDED Requirements

### Requirement: AudioEngine start_vad() accepts device parameter
`AudioEngine.start_vad()` SHALL accept an optional `device` parameter and forward it to `AudioEngine.start()`.

#### Scenario: start_vad passes device to start
- **WHEN** `start_vad(loop, threshold, callback, device="Headset Mic")` is called
- **THEN** the opened `sd.InputStream` SHALL use `device="Headset Mic"`
