## ADDED Requirements

### Requirement: Settings menu contains a Test Microphone entry
The settings modal SHALL include a "Test Microphone" list item that is always
visible when `AUDIO_AVAILABLE` is `True`, and hidden when it is `False`.

#### Scenario: Test Microphone item present when audio available
- **WHEN** `AUDIO_AVAILABLE` is `True` and the settings modal opens
- **THEN** the menu SHALL contain an entry labelled "Test Microphone"

#### Scenario: Test Microphone item absent when audio unavailable
- **WHEN** `AUDIO_AVAILABLE` is `False` and the settings modal opens
- **THEN** the menu SHALL NOT contain a "Test Microphone" entry

#### Scenario: Selecting Test Microphone opens MicTestScreen
- **WHEN** the user selects "Test Microphone" from the settings menu
- **THEN** `MicTestScreen` SHALL be pushed onto the screen stack as a modal
