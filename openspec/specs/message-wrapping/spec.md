## Requirements

### Requirement: Chat messages wrap to widget width
The `MessageView` widget SHALL render chat messages with automatic line wrapping
at word boundaries. Lines that exceed the widget's current width SHALL continue
on the next line rather than extending past the visible area.

#### Scenario: Long message wraps instead of overflowing
- **WHEN** a user sends a message longer than the terminal width
- **THEN** the message is displayed across multiple lines within the `MessageView` widget
- **THEN** no horizontal scrolling is required to read the full message

#### Scenario: Wrapping adapts to terminal resize
- **WHEN** the terminal window is resized to a narrower width after a long message is displayed
- **THEN** the `MessageView` re-renders existing and new messages wrapped to the new width

#### Scenario: Short messages are unaffected
- **WHEN** a user sends a message shorter than the terminal width
- **THEN** the message is displayed on a single line as before
