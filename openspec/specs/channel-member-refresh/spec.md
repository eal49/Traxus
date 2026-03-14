### Requirement: Member panel shows authoritative data on channel switch
When the user switches to a different text channel, the member panel SHALL
immediately clear any stale cached members and display the up-to-date member
list received from the server. The panel MUST NOT display members from the
previously viewed channel after the channel switch completes.

#### Scenario: Switch to unvisited channel
- **WHEN** the user clicks a channel they have not previously visited
- **THEN** the member panel clears immediately (shows empty list)
- **THEN** the member panel is populated with the current members once the server responds

#### Scenario: Switch to previously visited channel
- **WHEN** the user clicks a channel they have visited before
- **THEN** the member panel clears immediately (stale cache is not shown)
- **THEN** the member panel is populated with the fresh member list from the server

#### Scenario: Server user_list received after channel switch
- **WHEN** the server sends `S2C.USER_LIST` for the currently active channel
- **THEN** the member panel updates to reflect the received member list

### Requirement: Re-clicking the active channel refreshes members without side effects
When the user clicks on the channel that is already the active (current) channel,
the client SHALL request a fresh member list from the server without sending a
join request. No history SHALL be reloaded and no "Joined #channel" system
message SHALL appear.

#### Scenario: Click active channel
- **WHEN** the user clicks the channel name that matches `current_channel`
- **THEN** no `C2S.JOIN` is sent
- **THEN** a `C2S.LIST_MEMBERS` request is sent for that channel
- **THEN** the member panel updates with the fresh list when the server responds
- **THEN** no "Joined #channel" system message is appended to the message view

### Requirement: Server exposes LIST_MEMBERS message type
The server SHALL handle a `C2S.LIST_MEMBERS` message by sending a
`S2C.USER_LIST` response **only** to the requesting client (not a broadcast).
The handler SHALL NOT require the requesting client to be a member of the
channel, and SHALL NOT modify channel membership, history, or emit any
broadcast messages.

#### Scenario: Authenticated client requests members of a valid channel
- **WHEN** an authenticated client sends `{"type": "list_members", "channel": "<name>"}`
- **THEN** the server sends `S2C.USER_LIST` for that channel to the requesting client only
- **THEN** no other clients receive any message as a result

#### Scenario: LIST_MEMBERS for a non-existent channel
- **WHEN** an authenticated client sends `LIST_MEMBERS` for a channel that does not exist
- **THEN** the server sends `S2C.ERROR` with code `no_such_channel` to the requesting client

#### Scenario: LIST_MEMBERS before authentication
- **WHEN** an unauthenticated client sends `LIST_MEMBERS`
- **THEN** the server sends `S2C.ERROR` with code `not_authenticated`
