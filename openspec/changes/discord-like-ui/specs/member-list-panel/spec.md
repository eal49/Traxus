## MODIFIED Requirements

### Requirement: MemberPanel widget displays channel members
The `ChatScreen` SHALL include a `MemberPanel` widget on the right side of the layout showing all users known to the server, split into `ONLINE` and `OFFLINE` sections. The panel SHALL be populated from the server-wide roster provided in `auth_ok` and updated via `user_online` / `user_offline` events.

#### Scenario: Panel visible on ChatScreen
- **WHEN** the user is on `ChatScreen`
- **THEN** a `MemberPanel` widget SHALL be visible to the right of the message area, separated by a vertical border

#### Scenario: Panel shows all online users after auth
- **WHEN** the client receives `auth_ok` with an `online_users` list
- **THEN** the `MemberPanel` SHALL display each username from `online_users` under an `ONLINE — N` section header

#### Scenario: Panel shows offline users when auth is enabled
- **WHEN** the client receives `auth_ok` with registered users absent from `online_users`
- **THEN** the `MemberPanel` SHALL display those usernames under an `OFFLINE — N` section header in a dimmer style

### Requirement: MemberPanel updates live on join and leave
The `MemberPanel` SHALL reflect server-wide presence changes in real time via `user_online` and `user_offline` events.

#### Scenario: New user appears in Online section on connect
- **WHEN** the client receives a `user_online` event
- **THEN** the `MemberPanel` SHALL move that username to the `ONLINE` section (or add it if not previously known)

#### Scenario: User moves to Offline section on disconnect
- **WHEN** the client receives a `user_offline` event
- **THEN** the `MemberPanel` SHALL remove that username from the `ONLINE` section and, if the user was a known registered user, display them in the `OFFLINE` section

### Requirement: MemberPanel updates on nick change
The `MemberPanel` SHALL reflect nickname changes immediately.

#### Scenario: Member changes nick
- **WHEN** a `nick_changed` message arrives with `old_nick` matching a displayed member
- **THEN** the `MemberPanel` SHALL replace `old_nick` with `new_nick` in whichever section (Online or Offline) the user is currently displayed

### Requirement: MemberPanel indicates voice channel members
Members who are currently in a voice channel SHALL be visually distinguished in the Online section with an inline volume icon (`🔇/🔈/🔉/🔊`) and percentage label.

#### Scenario: Voice member shows icon and percentage in Online section
- **WHEN** a `voice_state` message arrives listing users in a voice channel
- **THEN** those users SHALL display an inline volume icon and percentage alongside their name in the Online section

#### Scenario: Voice indicator removed when user leaves voice
- **WHEN** a `channel_list` rebroadcast arrives and a previously voice-active user is no longer in any voice channel's `voice_members`
- **THEN** that user's volume indicator SHALL be removed from their row

### Requirement: MemberPanel uses Online/Offline two-section layout
The `MemberPanel` SHALL render an `ONLINE — N` section (all currently connected users) and, when at least one known-offline user exists, an `OFFLINE — N` section below it.

#### Scenario: Online section always present when connected
- **WHEN** the panel is rendered and the client is authenticated
- **THEN** an `ONLINE — N` section header SHALL appear with at least the local user's own name

#### Scenario: Offline section present only when populated
- **WHEN** at least one registered user is not currently connected
- **THEN** an `OFFLINE — N` section header SHALL appear below the Online section

#### Scenario: Sections are visually separated
- **WHEN** both sections are present
- **THEN** a blank line or dim separator SHALL appear between them

### Requirement: MemberPanel has consistent styling
The `MemberPanel` SHALL have a fixed width and dark theme styling consistent with the existing `ChannelSidebar`.

#### Scenario: Panel width and border
- **WHEN** `ChatScreen` is rendered
- **THEN** `MemberPanel` SHALL have a minimum width of 20 characters with a `border-left` separator

#### Scenario: Offline section uses dimmer text style
- **WHEN** offline users are rendered
- **THEN** their rows SHALL use a visually dimmer style (e.g., `[dim]`) compared to online user rows

## REMOVED Requirements

### Requirement: MemberPanel refreshes on channel switch
**Reason**: The panel now shows server-wide presence, not channel-scoped membership. Switching text channels has no effect on who is online.
**Migration**: Channel membership data is no longer needed for the right panel. The sidebar handles per-channel voice occupancy display.
