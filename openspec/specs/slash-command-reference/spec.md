## ADDED Requirements

### Requirement: Slash command reference document exists
The project SHALL contain `docs/commands.md` documenting every client slash command with its syntax, arguments, client-side effects, server messages triggered, and error conditions.

#### Scenario: Document covers all seven commands
- **WHEN** a developer opens `docs/commands.md`
- **THEN** they SHALL find entries for /join, /leave, /nick, /channels, /create, /help, and /quit

#### Scenario: Each command entry is complete
- **WHEN** a developer reads any single command entry
- **THEN** the entry SHALL include: syntax line, argument table (name / required / description), client-side parsing notes, server message(s) sent, server response(s) expected, and all documented error responses with their error codes

#### Scenario: Error conditions are explicit
- **WHEN** a command has a known error response
- **THEN** `docs/commands.md` SHALL list the S2C `error` message's `code` value and the condition that triggers it

### Requirement: Command syntax follows a consistent format
The `docs/commands.md` file SHALL present each command in a uniform structure so readers can scan predictably.

#### Scenario: Consistent section headings
- **WHEN** the document is rendered
- **THEN** each command SHALL appear under a `##` heading matching the command name (e.g., `## /join`)

#### Scenario: Arguments table present for parameterised commands
- **WHEN** a command accepts arguments
- **THEN** the entry SHALL include a Markdown table with columns: Argument, Required, Description

### Requirement: Slash command parsing rules documented
The `docs/commands.md` file SHALL describe how client-side parsing works so alternative client implementors can replicate the behaviour.

#### Scenario: Parsing rules section exists
- **WHEN** a developer reads `docs/commands.md`
- **THEN** they SHALL find a section explaining that text starting with `/` is treated as a command, command names are lowercased, arguments are split on whitespace, and bare `/` or `/ ` returns no command

#### Scenario: Unknown command behaviour documented
- **WHEN** a user types an unrecognised slash command
- **THEN** the document SHALL state that the client shows a local error message without sending anything to the server

---

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
