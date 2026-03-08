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
