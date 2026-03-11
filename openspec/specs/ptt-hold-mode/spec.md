### Requirement: PTT mode can be set to Toggle or Hold
The client SHALL support two PTT modes: Toggle (press once to start, press again to stop) and Hold (transmit only while the key or button is physically held).

#### Scenario: Default mode is Toggle
- **WHEN** no `ptt_mode` key exists in `~/.config/traxus/settings.json`
- **THEN** the client SHALL behave in Toggle mode

#### Scenario: Toggle mode flips transmit state on press
- **WHEN** `ptt_mode` is `"toggle"` and the user presses the PTT key or button
- **THEN** transmitting SHALL flip: off→on or on→off

#### Scenario: Hold mode starts transmitting on press
- **WHEN** `ptt_mode` is `"hold"` and the user presses the PTT key or button while not transmitting
- **THEN** the client SHALL start transmitting immediately

#### Scenario: Hold mode stops transmitting on release (mouse)
- **WHEN** `ptt_mode` is `"hold"`, the PTT binding is a mouse button, and the user releases that button
- **THEN** the client SHALL stop transmitting immediately

#### Scenario: Hold mode stops transmitting on release (keyboard)
- **WHEN** `ptt_mode` is `"hold"`, the PTT binding is a keyboard key, and the user releases the key (no further key events within 300 ms)
- **THEN** the client SHALL stop transmitting

#### Scenario: PTT mode is persisted
- **WHEN** the user changes PTT mode via `/settings`
- **THEN** the new mode SHALL be saved to `~/.config/traxus/settings.json` as `"ptt_mode": "toggle"` or `"ptt_mode": "hold"` and SHALL be restored on next launch
