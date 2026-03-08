## ADDED Requirements

### Requirement: Voice slash commands documented
`docs/commands.md` SHALL include entries for `/vcreate`, `/vjoin`, and `/vleave` following the same format as existing command entries.

#### Scenario: Document covers voice commands
- **WHEN** a developer opens `docs/commands.md`
- **THEN** they SHALL find entries for /vcreate, /vjoin, and /vleave alongside the existing seven commands

#### Scenario: /vjoin entry is complete
- **WHEN** a developer reads the /vjoin entry
- **THEN** the entry SHALL include syntax, argument table, C2S message sent (`voice_join`), S2C responses (`voice_state`), and error conditions (`no_such_channel`, `not_a_voice_channel`)

#### Scenario: /vleave entry is complete
- **WHEN** a developer reads the /vleave entry
- **THEN** the entry SHALL include syntax, the optional channel argument (defaults to current voice channel), C2S message sent (`voice_leave`), and S2C response (`voice_state`)

#### Scenario: /vcreate entry is complete
- **WHEN** a developer reads the /vcreate entry
- **THEN** the entry SHALL include syntax, name validation rules (`^[a-z0-9_-]{1,32}$`), C2S message sent, S2C responses (`channel_created`, `channel_list`), and error conditions (`invalid_channel_name`, `channel_exists`)

---

### Requirement: PTT keybinding documented in help output
The `/help` command output and `docs/commands.md` SHALL document the Ctrl+M push-to-talk toggle keybinding.

#### Scenario: /help mentions PTT
- **WHEN** the user runs /help
- **THEN** the output includes a line describing Ctrl+M as the PTT toggle
