## MODIFIED Requirements

### Requirement: MemberPanel indicates voice channel members
Members who are currently in a voice channel SHALL be displayed in a separate "In Voice" section below the text-channel member list, rather than inline with a 🎤 prefix in the main list.

#### Scenario: Voice members appear in a dedicated section
- **WHEN** a `voice_state` message arrives listing users in a voice channel
- **THEN** those users SHALL appear under an "In Voice" section header in the `MemberPanel` with a `🔊` prefix

#### Scenario: Voice section hidden when empty
- **WHEN** no users are in the voice channel (or no `voice_state` has been received)
- **THEN** the "In Voice" section header SHALL NOT be rendered

#### Scenario: Voice indicator removed when user leaves voice
- **WHEN** a `voice_state` message arrives and a previously-indicated user is no longer in the `users` array
- **THEN** that user SHALL be removed from the "In Voice" section

## ADDED Requirements

### Requirement: MemberPanel uses two-section layout
The `MemberPanel` SHALL render a "Members" section (text-channel presence) and optionally an "In Voice" section (voice-channel presence), instead of a single flat list.

#### Scenario: Members section always present
- **WHEN** the panel is rendered with at least one text-channel member
- **THEN** a "Members" section header SHALL appear followed by the member list

#### Scenario: In Voice section present only when populated
- **WHEN** the panel is rendered and at least one user is in the voice channel
- **THEN** an "In Voice" section header SHALL appear below the Members section

#### Scenario: Sections are visually separated
- **WHEN** both sections are present
- **THEN** a visual separator (dim horizontal rule or blank line) SHALL appear between them
