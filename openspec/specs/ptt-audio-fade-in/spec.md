### Requirement: PTT transmission applies fade-in ramp on activation
When PTT transitions from inactive (silence) to active (real audio), the system SHALL apply a linear amplitude ramp from 0.0 to 1.0 across the first transmitted audio frame (320 samples, 20 ms at 16 kHz) to eliminate the audible click caused by an abrupt silence-to-audio discontinuity.

#### Scenario: First real frame is faded in
- **WHEN** PTT activates and the first real PCM frame is emitted by `recv()`
- **THEN** the first sample of that frame SHALL have amplitude 0 and the last sample SHALL have full amplitude

#### Scenario: Subsequent consecutive frames are not faded
- **WHEN** PTT is already active and a real PCM frame follows another real PCM frame
- **THEN** the frame SHALL be passed through unmodified (no ramp applied)

#### Scenario: Re-activation after silence fades in again
- **WHEN** PTT deactivates (returning silence frames) and then reactivates
- **THEN** the first real frame after the silence gap SHALL receive the fade-in ramp again

### Requirement: MicFork applies the same fade-in ramp
The system SHALL apply the identical fade-in behaviour to `MicFork.recv()` so that every peer connection (fan-out branch) benefits equally from pop suppression.

#### Scenario: Fork first real frame is faded in
- **WHEN** a `MicFork` emits its first real PCM frame after a silence period
- **THEN** the first sample SHALL be 0 and the last sample SHALL be at full amplitude
