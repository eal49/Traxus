## ADDED Requirements

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
Members who are currently in a voice channel SHALL be visually distinguished.

#### Scenario: Voice member has indicator
- **WHEN** a `voice_state` message arrives listing a user as a voice channel member
- **THEN** that user's entry in the `MemberPanel` SHALL display a `🎤` prefix

#### Scenario: Voice indicator removed when user leaves voice
- **WHEN** a `voice_state` message arrives and a previously-indicated user is no longer in the `users` array
- **THEN** the `🎤` prefix SHALL be removed from that user's entry

### Requirement: MemberPanel refreshes on channel switch
When the user switches to a different text channel, the panel SHALL update to show that channel's members.

#### Scenario: Switching channels updates the panel
- **WHEN** the user joins a different channel and receives a new `user_list`
- **THEN** the `MemberPanel` SHALL replace its content with the new channel's member list

### Requirement: MemberPanel has consistent styling
The `MemberPanel` SHALL have a fixed width and dark theme styling consistent with the existing `ChannelSidebar`.

#### Scenario: Panel width and border
- **WHEN** `ChatScreen` is rendered
- **THEN** `MemberPanel` SHALL have a fixed width of 20 characters with a `border-left` separator

#### Scenario: Panel header
- **WHEN** the panel is rendered
- **THEN** a "Members" header SHALL appear at the top of the panel in muted text
