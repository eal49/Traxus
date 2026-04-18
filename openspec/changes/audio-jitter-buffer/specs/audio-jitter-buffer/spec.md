## ADDED Requirements

### Requirement: Fixed-delay jitter buffer for audio playback
The `AudioEngine` playback worker SHALL accumulate a configurable number of frames (`jitter_buffer_frames`) before starting to drain the play queue. Once primed, it SHALL drain at a fixed 20 ms clock. If the queue empties (underrun), the worker SHALL pause and re-enter the pre-fill gate on the next incoming frame.

#### Scenario: Playback does not start until buffer is primed
- **WHEN** audio frames begin arriving and the jitter buffer is empty
- **THEN** no audio is written to the output stream until `jitter_buffer_frames` frames are queued

#### Scenario: Playback drains at steady 20 ms clock once primed
- **WHEN** the jitter buffer has been primed and frames are arriving steadily
- **THEN** frames are written to the output stream at 20 ms intervals regardless of frame arrival timing

#### Scenario: Underrun re-enters pre-fill gate
- **WHEN** the play queue empties during playback (network gap)
- **THEN** the worker waits silently and resumes pre-fill when the next frame arrives

### Requirement: Drop-newest overflow strategy
When the play queue is full, `AudioEngine.play()` SHALL discard the incoming frame rather than removing an already-buffered frame from the queue.

#### Scenario: Incoming frame discarded when queue is full
- **WHEN** `AudioEngine.play()` is called and `_play_queue` is at max capacity
- **THEN** the new frame SHALL be silently discarded
- **THEN** the frames already in the queue SHALL remain unchanged

#### Scenario: Drop-newest does not raise
- **WHEN** the play queue is full and a new frame arrives
- **THEN** no exception is raised and `play()` returns immediately

### Requirement: Explicit low-latency output stream
The `sd.OutputStream` opened by `_playback_worker` SHALL be created with `latency="low"` to prevent OS-default over-buffering.

#### Scenario: OutputStream created with low latency
- **WHEN** `_playback_worker` opens the output stream
- **THEN** the stream SHALL be initialized with `latency="low"`

### Requirement: Configurable jitter buffer depth
The jitter buffer depth SHALL be configurable via `jitter_buffer_frames` in `settings.json`. The default value SHALL be `3` (60 ms at 20 ms frame size). The `AudioEngine` SHALL read this value on startup.

#### Scenario: Default depth of 3 applied when no setting present
- **WHEN** `settings.json` does not contain `jitter_buffer_frames`
- **THEN** the jitter buffer depth SHALL default to `3`

#### Scenario: Custom depth respected
- **WHEN** `settings.json` contains `jitter_buffer_frames: 1`
- **THEN** playback begins after only 1 frame is queued
