## ADDED Requirements

### Requirement: Tab completes slash-command names
When the input bar contains a partial slash command (text starting with `/` followed by at least one character), pressing Tab SHALL cycle forward through alphabetically sorted command names that match the prefix. Shift+Tab SHALL cycle backward.

#### Scenario: Single match completes immediately
- **WHEN** the user types a prefix that matches exactly one command and presses Tab
- **THEN** the input field SHALL contain the full command name and no cycling state is entered

#### Scenario: Multiple matches cycle forward on Tab
- **WHEN** the user types a prefix matching multiple commands and presses Tab
- **THEN** the input SHALL display the first (alphabetically earliest) matching command

#### Scenario: Repeated Tab presses cycle through all matches
- **WHEN** the user presses Tab again while cycling
- **THEN** the input SHALL advance to the next matching command, wrapping from last back to first

#### Scenario: Shift+Tab cycles backward
- **WHEN** the user presses Shift+Tab while cycling
- **THEN** the input SHALL display the previous matching command, wrapping from first back to last

#### Scenario: No match is a no-op
- **WHEN** the typed prefix matches no known command and the user presses Tab
- **THEN** the input value SHALL remain unchanged

#### Scenario: Bare slash is a no-op
- **WHEN** the input contains only `/` (no characters after it) and the user presses Tab
- **THEN** the input value SHALL remain unchanged

#### Scenario: Non-slash input is a no-op
- **WHEN** the input does not start with `/` and the user presses Tab
- **THEN** the input value SHALL remain unchanged

### Requirement: Draft prefix is preserved and restored on Escape
The input value at the moment Tab is first pressed (the prefix) SHALL be saved internally. Pressing Escape while cycling SHALL restore that prefix and exit cycling.

#### Scenario: Escape restores the original prefix
- **WHEN** the user has cycled to a completion and presses Escape
- **THEN** the input SHALL revert to the text that was present before any Tab was pressed, and cycling SHALL stop

#### Scenario: Escape outside cycling is a no-op
- **WHEN** the user is not cycling completions and presses Escape
- **THEN** the input value SHALL remain unchanged and Escape SHALL not be consumed

### Requirement: Typing exits cycling mode
When the user types any character while cycling through completions, cycling SHALL stop and the typed character SHALL be appended to the currently displayed completion normally.

#### Scenario: Typing a character after Tab exits cycling
- **WHEN** the user presses Tab to cycle to a completion and then types a character
- **THEN** cycling SHALL stop and the character SHALL be inserted into the input as normal

### Requirement: Completed commands do not include a trailing space
Tab completion SHALL insert the command name only, without appending a trailing space.

#### Scenario: Completion ends at command name boundary
- **WHEN** Tab completes `/join`
- **THEN** the input value SHALL be `/join` with no trailing space
