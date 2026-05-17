## Requirements

### Requirement: AudioEngine tracks per-user volume levels
`AudioEngine` SHALL maintain a `_per_user_volume` dict mapping username strings to integer percentage levels (0–200, default 100). The dict SHALL be readable and writable via `get_volume(username)` and `set_volume(username, level)` methods. `set_volume` SHALL clamp the supplied level to [0, 200].

#### Scenario: Default volume for unknown user is 100
- **WHEN** `get_volume` is called with a username not in the dict
- **THEN** it SHALL return 100

#### Scenario: set_volume stores the level
- **WHEN** `set_volume("alice", 80)` is called
- **THEN** `get_volume("alice")` SHALL return 80

#### Scenario: set_volume clamps below 0
- **WHEN** `set_volume("alice", -10)` is called
- **THEN** `get_volume("alice")` SHALL return 0

#### Scenario: set_volume clamps above 200
- **WHEN** `set_volume("alice", 250)` is called
- **THEN** `get_volume("alice")` SHALL return 200

---

### Requirement: AudioEngine.play accepts a username argument
`AudioEngine.play()` SHALL accept an optional `username: str = ""` parameter. The value SHALL be passed through to the internal playback queue so the playback worker can look up the gain for that user.

#### Scenario: play called without username uses default gain
- **WHEN** `play(audio_bytes, codec)` is called with no username
- **THEN** the frame SHALL be played at 100% gain (unmodified)

#### Scenario: play called with username uses stored gain
- **WHEN** `set_volume("alice", 50)` has been called and `play(audio_bytes, codec, "alice")` is called
- **THEN** the decoded PCM SHALL be scaled by 0.5 before being written to the output stream

---

### Requirement: Per-participant volume applies a squared power-law gain curve
The gain applied in `RemoteAudioSink` SHALL follow a squared power-law curve:
`gain = (level / 100) ** 2`, where `level` is the integer volume value (0–200).
This matches perceptual loudness expectations: 100 % is unity (0 dB), 200 % is
+12 dB (4×), and 50 % is −12 dB (0.25×). A `level` of exactly 100 SHALL bypass
the multiply entirely (fast-path).

#### Scenario: 200 % volume delivers approximately +12 dB boost
- **WHEN** the volume for a participant is set to 200
- **THEN** each decoded PCM sample SHALL be multiplied by 4.0 (clipped to int16 range)

#### Scenario: 100 % volume is unity gain
- **WHEN** the volume for a participant is set to 100
- **THEN** the PCM samples SHALL be passed through unchanged (no multiply)

#### Scenario: 50 % volume quarters amplitude
- **WHEN** the volume for a participant is set to 50
- **THEN** each decoded PCM sample SHALL be multiplied by 0.25

#### Scenario: 0 % volume produces silence
- **WHEN** the volume for a participant is set to 0
- **THEN** all PCM samples SHALL be zero regardless of input level

---

### Requirement: MemberPanel displays per-user volume bars for voice participants
`MemberPanel` SHALL render each user currently in a voice channel with a 10-block Unicode bar and an integer percentage label. The bar SHALL reflect the current volume level stored in `AudioEngine`: 0 filled blocks at 0%, 5 filled blocks at 100% (default), 10 filled blocks at 200%.

#### Scenario: Default volume renders as half-filled bar
- **WHEN** a voice user has not had their volume adjusted
- **THEN** their row SHALL display exactly 5 filled (`█`) and 5 empty (`░`) blocks followed by `100%`

#### Scenario: Bar reflects set_volume changes
- **WHEN** `set_volume("alice", 40)` is called and the panel re-renders
- **THEN** alice's row SHALL display 2 filled blocks and 8 empty blocks followed by `40%`

#### Scenario: Text-channel members have no volume bar
- **WHEN** a member appears in the text-channel members list but not the in-voice list
- **THEN** their row SHALL NOT display a volume bar or percentage

---

### Requirement: MemberPanel is keyboard-navigable for volume adjustment
`MemberPanel` SHALL be focusable (`can_focus = True`). When focused and voice users are present, ↑/↓ SHALL move a visible cursor among voice-user rows. ← SHALL decrease the selected user's volume by 10% (floor 0%). → SHALL increase it by 10% (ceil 200%). Each adjustment SHALL immediately call `AudioEngine.set_volume` and re-render the panel.

#### Scenario: Up/Down moves cursor among voice users
- **WHEN** the panel is focused and the user presses ↓
- **THEN** the cursor SHALL move to the next voice-user row (wrapping at the bottom to the top)

#### Scenario: Left decreases volume by 10
- **WHEN** the panel is focused and the current user's volume is 80 and the user presses ←
- **THEN** `AudioEngine.get_volume` for that user SHALL return 70 and the bar SHALL update

#### Scenario: Right increases volume by 10
- **WHEN** the panel is focused and the current user's volume is 80 and the user presses →
- **THEN** `AudioEngine.get_volume` for that user SHALL return 90 and the bar SHALL update

#### Scenario: Left at 0% does not go below 0
- **WHEN** the panel is focused and the current user's volume is 0 and the user presses ←
- **THEN** `AudioEngine.get_volume` for that user SHALL return 0

#### Scenario: Right at 200% does not go above 200
- **WHEN** the panel is focused and the current user's volume is 200 and the user presses →
- **THEN** `AudioEngine.get_volume` for that user SHALL return 200

#### Scenario: No crash when no voice users are present
- **WHEN** the panel is focused and there are no users in voice and any arrow key is pressed
- **THEN** no exception SHALL be raised and the panel SHALL remain unchanged
