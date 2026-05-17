## ADDED Requirements

### Requirement: channel_list includes voice_members per voice channel
Each voice channel entry in the `channel_list` S2C payload SHALL include a `voice_members` field containing an array of usernames currently in that voice channel. Text channel entries SHALL omit this field.

#### Scenario: voice_members present for occupied voice channel
- **WHEN** the server sends a `channel_list` response and alice is in voice channel "main"
- **THEN** the "main" channel object SHALL include `"voice_members": ["alice"]`

#### Scenario: voice_members empty for unoccupied voice channel
- **WHEN** no users are in a voice channel
- **THEN** that channel's `channel_list` entry SHALL include `"voice_members": []`

#### Scenario: text channel entries have no voice_members field
- **WHEN** the server sends a `channel_list` response
- **THEN** text channel entries SHALL NOT include a `voice_members` field

### Requirement: Server re-broadcasts channel_list to all clients on voice state change
When any client joins or leaves a voice channel, the server SHALL broadcast an updated `channel_list` to every connected client reflecting the new voice membership.

#### Scenario: channel_list broadcast on voice join
- **WHEN** a client sends `voice_join` and joins a voice channel successfully
- **THEN** every connected client SHALL receive an updated `channel_list` with the new member's username in that channel's `voice_members`

#### Scenario: channel_list broadcast on voice leave
- **WHEN** a client sends `voice_leave`
- **THEN** every connected client SHALL receive an updated `channel_list` with the departed member removed from that channel's `voice_members`

#### Scenario: channel_list broadcast on client disconnect while in voice
- **WHEN** a client disconnects while it is a member of a voice channel
- **THEN** every remaining connected client SHALL receive an updated `channel_list` with that client removed from the voice channel's `voice_members`

### Requirement: ChannelSidebar renders members nested under each voice channel
The `ChannelSidebar` widget SHALL display the current voice occupants of each voice channel as indented rows directly below the channel name row, using voice membership data from the latest `channel_list` payload. These rows SHALL be non-interactive (display only).

#### Scenario: Occupied voice channel shows nested member rows
- **WHEN** a `channel_list` update arrives with alice and bob in voice channel "main"
- **THEN** the sidebar SHALL render "main" followed by two indented rows: "  · alice" and "  · bob"

#### Scenario: Empty voice channel shows no nested rows
- **WHEN** a voice channel has an empty `voice_members` array
- **THEN** the sidebar SHALL render only the channel name row with no children

#### Scenario: Nested rows are non-interactive
- **WHEN** the user clicks or navigates to a nested member row in the sidebar
- **THEN** no channel selection event SHALL be emitted and focus SHALL not change

#### Scenario: Voice member rows update on channel_list rebroadcast
- **WHEN** a new `channel_list` arrives with changed `voice_members`
- **THEN** the sidebar SHALL immediately re-render the updated occupant rows without requiring a page reload or manual action
