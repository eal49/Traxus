# quote-command Specification

## Purpose
TBD - created by archiving change message-line-selection. Update Purpose after archive.
## Requirements
### Requirement: /quote command is registered
The client SHALL recognise `/quote` as a known slash command and include it in the help text.

#### Scenario: /quote appears in /help output
- **WHEN** the user runs `/help`
- **THEN** the output SHALL include an entry for `/quote` describing its purpose

#### Scenario: /quote with no space does not activate selection
- **WHEN** the user types `/quote` and presses Enter without a trailing space
- **THEN** the command SHALL be treated as unknown or show a usage hint
- **THEN** no selection mode SHALL be activated

### Requirement: /quote activates line selection and inserts a quoted reference
After the user selects a line via the selection cursor, `/quote` SHALL insert an IRC-style quoted reference into the InputBar so the user can append their reply and send it.

#### Scenario: Selected chat line produces IRC-style quote
- **WHEN** the user activates `/quote` selection mode and presses Enter on a chat line from user "alice" with content "hello world"
- **THEN** the InputBar SHALL be populated with `> @alice: hello world`
- **THEN** the cursor SHALL be placed at the end of the input so the user can type their reply

#### Scenario: Selecting a system/local message with /quote
- **WHEN** the user activates `/quote` selection mode and presses Enter on a line that has no associated payload (system message or local echo)
- **THEN** the InputBar SHALL be populated using the plain text of that line without a username prefix (e.g. `> hello world`)

#### Scenario: Quote text is not sent automatically
- **WHEN** the InputBar is populated by /quote
- **THEN** no message SHALL be sent to the server; the user must press Enter again to send

