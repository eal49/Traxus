## MODIFIED Requirements

### Requirement: VAD sensitivity is user-configurable
The VAD RMS energy threshold SHALL be adjustable via four named levels or a custom numeric value, all persisted to settings.

#### Scenario: Low sensitivity requires loud speech
- **WHEN** VAD sensitivity is `"low"`
- **THEN** only high-energy audio (RMS ≥ 200 on int16 scale) SHALL trigger transmission

#### Scenario: Medium sensitivity is balanced
- **WHEN** VAD sensitivity is `"medium"`
- **THEN** moderate-energy audio (RMS ≥ 100) SHALL trigger transmission

#### Scenario: High sensitivity (default) detects quiet speech
- **WHEN** VAD sensitivity is `"high"`
- **THEN** low-energy audio (RMS ≥ 50) SHALL trigger transmission

#### Scenario: Very high sensitivity detects whispers
- **WHEN** VAD sensitivity is `"very_high"`
- **THEN** very low-energy audio (RMS ≥ 20) SHALL trigger transmission

#### Scenario: Custom sensitivity uses saved numeric threshold
- **WHEN** VAD sensitivity is `"custom"`
- **THEN** the RMS threshold SHALL be read from `vad_custom_threshold` in settings (default 50.0)

#### Scenario: Default sensitivity is high
- **WHEN** no `vad_sensitivity` key exists in settings
- **THEN** the client SHALL behave as if sensitivity is `"high"`

#### Scenario: Default custom threshold is 50.0
- **WHEN** `vad_sensitivity` is `"custom"` and no `vad_custom_threshold` key exists in settings
- **THEN** the client SHALL use a threshold of 50.0
