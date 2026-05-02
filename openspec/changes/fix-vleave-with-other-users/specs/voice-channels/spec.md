## MODIFIED Requirements

### Requirement: Server notifies the leaving client of voice_state on vleave
When a client sends `C2S voice_leave`, the server SHALL send a `S2C voice_state`
message to the leaving client with an **empty** `users` list, regardless of how
many participants remain in the channel. This signals departure unambiguously.
The remaining participants SHALL receive the normal roster (all members still
present, excluding the leaver).

#### Scenario: Leaving client receives empty users when others remain
- **WHEN** Alice sends `C2S voice_leave { channel: "lounge" }` while Bob is still in the channel
- **THEN** Alice SHALL receive `S2C voice_state { channel: "lounge", users: [] }`
- **THEN** Bob SHALL receive `S2C voice_state { channel: "lounge", users: [bob] }`

#### Scenario: Leaving client receives empty users when channel is now empty
- **WHEN** the last client sends `C2S voice_leave { channel: "lounge" }`
- **THEN** that client SHALL receive `S2C voice_state { channel: "lounge", users: [] }`

#### Scenario: Remaining members also receive voice_state
- **WHEN** a client sends `C2S voice_leave { channel: "lounge" }`
- **THEN** all other clients still in `#lounge` voice SHALL also receive `S2C voice_state`
- **THEN** their `users` list SHALL NOT contain the leaving client's username
