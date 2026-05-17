## Requirements

### Requirement: MemberPanel widget displays channel members
The `ChatScreen` SHALL include a `MemberPanel` widget on the right side of the layout showing all members of the currently active text channel.

#### Scenario: Panel visible on ChatScreen
- **WHEN** the user is on `ChatScreen`
- **THEN** a `MemberPanel` widget SHALL be visible to the right of the message area, separated by a vertical border

#### Scenario: Panel shows members after joining a channel
- **WHEN** the client receives a `user_list` message for the active channel
- **THEN** the `MemberPanel` SHALL display each username from the `users` array, one per line

#### Scenario: Panel is empty before joining
- **WHEN** the user is on `ChatScreen` but no `user_list` has been received for the active channel
- **THEN** the `MemberPanel` SHALL display a header with no member entries

### Requirement: MemberPanel updates live on join and leave
The `MemberPanel` SHALL reflect membership changes in real time without requiring a channel rejoin.

#### Scenario: New user joins the channel
- **WHEN** a `system` message arrives containing `"<username> joined #<channel>"` for the active channel
- **THEN** the `MemberPanel` SHALL add that username to the displayed list

#### Scenario: User leaves the channel
- **WHEN** a `system` message arrives containing `"<username> left #<channel>"` for the active channel
- **THEN** the `MemberPanel` SHALL remove that username from the displayed list

#### Scenario: User disconnects
- **WHEN** a `system` message arrives containing `"<username> disconnected"` while that user is in the active channel's member list
- **THEN** the `MemberPanel` SHALL remove that username from the displayed list

### Requirement: MemberPanel updates on nick change
The `MemberPanel` SHALL reflect nickname changes immediately.

#### Scenario: Member changes nick
- **WHEN** a `nick_changed` message arrives with `old_nick` matching a displayed member
- **THEN** the `MemberPanel` SHALL replace `old_nick` with `new_nick` in the list

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

### Requirement: MemberPanel refreshes on channel switch
When the user switches to a different text channel, the panel SHALL update to show that channel's members.

#### Scenario: Switching channels updates the panel
- **WHEN** the user joins a different channel and receives a new `user_list`
- **THEN** the `MemberPanel` SHALL replace its content with the new channel's member list

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

### Requirement: MemberPanel has consistent styling
The `MemberPanel` SHALL have a fixed width and dark theme styling consistent with the existing `ChannelSidebar`.

#### Scenario: Panel width and border
- **WHEN** `ChatScreen` is rendered
- **THEN** `MemberPanel` SHALL have a fixed width of 20 characters with a `border-left` separator

#### Scenario: Panel header
- **WHEN** the panel is rendered
- **THEN** a "Members" header SHALL appear at the top of the panel in muted text
