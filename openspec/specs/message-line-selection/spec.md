# message-line-selection Specification

## Purpose
TBD - created by archiving change message-line-selection. Update Purpose after archive.
## Requirements
### Requirement: MessageView maintains a parallel payload store
`MessageView` SHALL store a `_payloads: list[dict | None]` in lockstep with its `_lines` list, where each entry is the raw server payload for that line or `None` for system/local messages.

#### Scenario: Chat message stores payload
- **WHEN** `add_chat(payload)` is called with a server chat payload
- **THEN** the payload SHALL be appended to `_payloads` at the same index as the rendered markup line

#### Scenario: System message stores None
- **WHEN** a system or local message is appended to MessageView
- **THEN** `None` SHALL be appended to `_payloads` at the corresponding index

#### Scenario: Payload store length matches line store
- **WHEN** any number of lines have been added
- **THEN** `len(_payloads)` SHALL always equal `len(_lines)`

### Requirement: Selection mode activates when InputBar detects a selection command with trailing space
When the user types `/quote ` or `/pin ` (command word followed by exactly one space and no other text) in the input bar, the app SHALL enter line-selection mode.

#### Scenario: Typing /quote followed by space activates selection mode
- **WHEN** the InputBar value becomes exactly `/quote ` (the word "quote" after the slash, followed by a single space)
- **THEN** the app SHALL enter line-selection mode with cursor on the last visible line
- **THEN** the InputBar SHALL be cleared and disabled until selection completes

#### Scenario: Typing /pin followed by space activates selection mode
- **WHEN** the InputBar value becomes exactly `/pin ` (the word "pin" after the slash, followed by a single space)
- **THEN** the app SHALL enter line-selection mode with cursor on the last visible line
- **THEN** the InputBar SHALL be cleared and disabled until selection completes

#### Scenario: Partial commands do not activate selection mode
- **WHEN** the InputBar value is `/quote` (no trailing space) or `/pin` (no trailing space)
- **THEN** selection mode SHALL NOT be activated

### Requirement: Keyboard navigation moves the selection cursor
While in line-selection mode the user SHALL navigate the message history with Up and Down arrow keys.

#### Scenario: Up arrow moves cursor up
- **WHEN** selection mode is active and the user presses Up
- **THEN** the cursor SHALL move to the previous line (index decremented by 1, minimum 0)

#### Scenario: Down arrow moves cursor down
- **WHEN** selection mode is active and the user presses Down
- **THEN** the cursor SHALL move to the next line (index incremented by 1, maximum last line)

#### Scenario: Cursor line is visually highlighted
- **WHEN** the cursor is on a line
- **THEN** that line SHALL be rendered with a distinct highlight (e.g. reverse-video or background colour) so the user can clearly see which line is selected

### Requirement: Enter confirms the selection and exits selection mode
Pressing Enter while in selection mode SHALL complete the pending command action and return focus to the InputBar.

#### Scenario: Enter triggers the pending command
- **WHEN** selection mode is active and the user presses Enter
- **THEN** the action corresponding to the triggering command (/quote or /pin) SHALL be executed on the currently highlighted line
- **THEN** selection mode SHALL be deactivated and the InputBar SHALL regain focus

### Requirement: Escape cancels selection mode without any action
Pressing Escape while in selection mode SHALL exit selection mode cleanly.

#### Scenario: Escape deactivates selection mode
- **WHEN** selection mode is active and the user presses Escape
- **THEN** selection mode SHALL be deactivated with no command action taken
- **THEN** the InputBar SHALL regain focus with its previous content restored (empty if it was empty)
- **THEN** the cursor highlight SHALL be removed from the message view

