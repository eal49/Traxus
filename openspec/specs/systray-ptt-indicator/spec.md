# systray-ptt-indicator Specification

## Purpose

Define the behaviour of the system tray icon that reflects live connection and PTT state, including icon states, update timing, graceful degradation, and the right-click Quit action.
## Requirements
### Requirement: Tray icon appears on launch
The client SHALL display a system tray icon immediately after launch, using the
`Disconnected` icon as the initial state.

#### Scenario: Icon visible on startup
- **WHEN** the client process starts
- **THEN** a system tray icon SHALL appear in the OS notification area within 2 seconds

#### Scenario: Icon removed on exit
- **WHEN** the client process exits (via `/quit`, closing the terminal, or the tray Quit action)
- **THEN** the system tray icon SHALL be removed from the notification area

### Requirement: Icon reflects connection state
The tray icon SHALL change to reflect the current server connection state.

#### Scenario: Disconnected state
- **WHEN** `connection_state` is `"disconnected"` or `"reconnecting"`
- **THEN** the tray icon SHALL show the `Disconnected` image

#### Scenario: Connected but not in voice
- **WHEN** `connection_state` is `"connected"` AND the client is not in a voice channel
- **THEN** the tray icon SHALL show the `Connected` image

### Requirement: Icon reflects voice channel and PTT state
When the client is in a voice channel, the tray icon SHALL reflect the precise PTT state.

#### Scenario: Voice channel joined, mic idle
- **WHEN** the client is in a voice channel AND is not transmitting AND PTT mode is not VAD
- **THEN** the tray icon SHALL show the `VoiceConnected` image

#### Scenario: VAD mode monitoring below threshold
- **WHEN** the client is in a voice channel AND PTT mode is `"vad"` AND VAD is active
  AND audio energy is below the transmission threshold (not transmitting)
- **THEN** the tray icon SHALL show the `Listening` image

#### Scenario: Transmitting, alone in channel
- **WHEN** the client is transmitting AND there are no other participants in the voice channel
- **THEN** the tray icon SHALL show the `Speaking` image

#### Scenario: Transmitting, others present
- **WHEN** the client is transmitting AND at least one other participant is in the voice channel
- **THEN** the tray icon SHALL show the `SpeakingAndListening` image

### Requirement: Tray icon updates are immediate
State transitions SHALL be reflected in the tray icon with no perceptible delay
(within the same event-loop tick that triggers the state change).

#### Scenario: PTT start reflects immediately
- **WHEN** the user activates PTT (F9 press or VAD onset)
- **THEN** the tray icon SHALL update to `Speaking` or `SpeakingAndListening` before
  the next audio frame is transmitted

#### Scenario: Disconnect reflects immediately
- **WHEN** the WebSocket connection drops
- **THEN** the tray icon SHALL update to `Disconnected` within the same
  `connection_state` reactive update

### Requirement: Tray right-click menu contains Quit action
The tray icon SHALL have a right-click context menu with a single **Quit** item
that exits the application cleanly.

#### Scenario: Quit from tray
- **WHEN** the user right-clicks the tray icon and selects **Quit**
- **THEN** the application SHALL exit, closing the WebSocket connection and removing the icon

### Requirement: Graceful degradation when pystray or Pillow unavailable
If `pystray` or `Pillow` cannot be imported, the client SHALL start normally without
a tray icon. No error message SHALL be shown to the user.

#### Scenario: Missing pystray
- **WHEN** `pystray` is not installed
- **THEN** the client launches successfully
- **THEN** no system tray icon appears
- **THEN** all text and voice features function normally

#### Scenario: Missing Pillow
- **WHEN** `Pillow` is not installed but `pystray` is
- **THEN** the client launches successfully without a tray icon

