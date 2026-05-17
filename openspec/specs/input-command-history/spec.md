## Requirements

### Requirement: Up/Down arrows navigate slash-command history
When the input bar is focused, pressing Up/Down SHALL cycle through previously submitted slash commands. Only entries beginning with `/` are stored; plain chat messages SHALL NOT appear in history.

#### Scenario: Up arrow recalls most recent command
- **WHEN** the user has submitted at least one slash command and presses Up in the input bar
- **THEN** the input field SHALL display the most recently submitted slash command

#### Scenario: Repeated Up presses step further back
- **WHEN** the user presses Up multiple times
- **THEN** each press SHALL display the next older slash command in sequence

#### Scenario: Up at oldest entry is a no-op
- **WHEN** the user has navigated to the oldest history entry and presses Up again
- **THEN** the input value SHALL remain unchanged

#### Scenario: Down returns toward present
- **WHEN** the user has navigated back in history and presses Down
- **THEN** each press SHALL display the next newer slash command

#### Scenario: Down past newest restores the draft
- **WHEN** the user presses Down past the most recent history entry
- **THEN** the input field SHALL be restored to whatever the user was typing before navigating

#### Scenario: Plain chat messages are excluded from history
- **WHEN** the user submits a plain message (not starting with `/`)
- **THEN** it SHALL NOT be added to the command history

#### Scenario: Up/Down are no-ops when history is empty
- **WHEN** no slash commands have been submitted yet and the user presses Up or Down
- **THEN** the input value SHALL remain unchanged

### Requirement: Draft is preserved while navigating history
When the user begins navigating history, the current contents of the input field SHALL be saved and restored when they navigate back to the present position.

#### Scenario: Draft saved on first Up press
- **WHEN** the user has partially typed text and presses Up
- **THEN** the partially typed text SHALL be saved internally

#### Scenario: Draft restored on Down past newest
- **WHEN** the user navigates back to the present (Down past the newest entry)
- **THEN** the input field SHALL contain exactly what was typed before navigating

#### Scenario: Draft cleared on submit
- **WHEN** the user submits a command while in the history or at the current position
- **THEN** the history position SHALL reset to "current" and the saved draft SHALL be cleared

### Requirement: Consecutive duplicate commands are suppressed
The same slash command submitted twice in a row SHALL be stored only once.

#### Scenario: Consecutive duplicate not added
- **WHEN** the user submits `/vjoin lounge` and then `/vjoin lounge` again immediately
- **THEN** only one entry for `/vjoin lounge` SHALL exist at the end of the history

#### Scenario: Non-consecutive duplicate is kept
- **WHEN** the user submits `/vjoin lounge`, then `/nick alice`, then `/vjoin lounge`
- **THEN** both `/vjoin lounge` entries SHALL exist (they are not adjacent)

### Requirement: History is persisted across restarts
Slash-command history SHALL be saved to `~/.traxus/command_history.json` after each relevant submit and loaded on client startup.

#### Scenario: History survives restart
- **WHEN** the user submits slash commands and restarts the client
- **THEN** the previously submitted commands SHALL be available via Up arrow

#### Scenario: Missing history file starts empty
- **WHEN** `command_history.json` does not exist on startup
- **THEN** the client SHALL start with an empty history and not crash

#### Scenario: Corrupt history file starts empty
- **WHEN** `command_history.json` contains invalid JSON
- **THEN** the client SHALL start with an empty history and not crash

### Requirement: History is capped at 200 entries
The history list SHALL contain at most 200 entries. When a new entry would exceed the cap, the oldest entry SHALL be evicted.

#### Scenario: Oldest entry evicted at cap
- **WHEN** 200 entries are stored and a new slash command is submitted
- **THEN** the oldest entry SHALL be removed and the new entry SHALL be appended
