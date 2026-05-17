## ADDED Requirements

### Requirement: Right panel displays server-wide Online and Offline sections
The `MemberPanel` widget SHALL display all users known to the server in two labelled sections: `ONLINE — N` (currently connected) and `OFFLINE — N` (registered but not connected). Each section header SHALL include a live count. Online members SHALL appear first.

#### Scenario: Online section lists all connected users
- **WHEN** three users are connected to the server
- **THEN** the panel SHALL show `ONLINE — 3` followed by three member rows

#### Scenario: Offline section lists registered-but-absent users
- **WHEN** one registered user is not connected and auth is enabled
- **THEN** the panel SHALL show an `OFFLINE — 1` section with that username rendered in a dimmer style

#### Scenario: Offline section absent when auth is disabled
- **WHEN** the server is running without `TRAXUS_USERS`
- **THEN** the panel SHALL show no `OFFLINE` section (the concept of "known offline users" does not exist without a user store)

#### Scenario: Own username appears in Online section
- **WHEN** the local user is connected
- **THEN** their username SHALL appear in the `ONLINE` section alongside peers

### Requirement: Voice-active users in the Online section display a volume indicator
For each user in the Online section who is currently in a voice channel, the panel SHALL render an inline volume icon and percentage label. Non-voice online users and all offline users SHALL have no volume indicator.

#### Scenario: Voice user row includes icon and percentage
- **WHEN** alice is online and in a voice channel and her volume is 100
- **THEN** alice's row SHALL display `🔉 100%` (or the appropriate tier icon)

#### Scenario: Volume icon reflects tier correctly
- **WHEN** a voice user's volume is 0
- **THEN** their icon SHALL be `🔇`
- **WHEN** a voice user's volume is between 1 and 50
- **THEN** their icon SHALL be `🔈`
- **WHEN** a voice user's volume is between 51 and 149
- **THEN** their icon SHALL be `🔉`
- **WHEN** a voice user's volume is between 150 and 200
- **THEN** their icon SHALL be `🔊`

#### Scenario: Non-voice online user has no volume indicator
- **WHEN** bob is online but not in any voice channel
- **THEN** bob's row SHALL display only his username with no icon or percentage

#### Scenario: Volume indicator updates immediately on adjustment
- **WHEN** the user presses ← or → to adjust a voice participant's volume
- **THEN** the icon and percentage in that user's row SHALL update on the next render

### Requirement: Panel is keyboard-navigable for volume adjustment
The `MemberPanel` SHALL be focusable. When focused, ↑/↓ SHALL move a cursor among the voice-active users in the Online section only. ← SHALL decrease the selected user's volume by 10 (floor 0). → SHALL increase it by 10 (ceil 200). Each adjustment SHALL immediately call `PeerManager.set_volume` and re-render the panel.

#### Scenario: ↑/↓ navigates among voice users only
- **WHEN** the panel is focused and alice and bob are voice-active
- **THEN** ↓ SHALL move the cursor to the next voice user (wrapping at the bottom)
- **THEN** ↑ SHALL move the cursor to the previous voice user (wrapping at the top)

#### Scenario: Non-voice users are skipped during navigation
- **WHEN** the panel is focused and cursor navigation is active
- **THEN** pressing ↓ or ↑ SHALL only stop on voice-active user rows, never on text-only or offline rows

#### Scenario: ← decreases volume and updates indicator
- **WHEN** the cursor is on alice with volume 80 and the user presses ←
- **THEN** alice's volume SHALL become 70 and her row SHALL re-render with the updated icon and percentage

#### Scenario: → increases volume and updates indicator
- **WHEN** the cursor is on alice with volume 80 and the user presses →
- **THEN** alice's volume SHALL become 90 and her row SHALL re-render with the updated icon and percentage

#### Scenario: No crash when no voice users are present
- **WHEN** the panel is focused and no users are in any voice channel
- **THEN** pressing any arrow key SHALL produce no exception and the panel SHALL remain unchanged
