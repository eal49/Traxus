## Requirements

### Requirement: Channel type field
Every channel SHALL carry a `type` field with value `"text"` or `"voice"`. Existing channels bootstrapped at startup (general, random, dev) SHALL default to `"text"`. The `/vcreate` command creates channels with `type: "voice"`.

#### Scenario: Default channels are text type
- **WHEN** the server starts
- **THEN** the three default channels (#general, #random, #dev) each have `type: "text"`

#### Scenario: Voice channel creation sets type
- **WHEN** a client sends `C2S voice_create` (or `C2S create` with `channel_type: "voice"`)
- **THEN** the new channel has `type: "voice"` in ChannelRegistry

---

### Requirement: Voice channel membership tracking
The server SHALL maintain a separate voice membership set per voice channel, independent of text channel subscriptions. A client MAY be subscribed to a text channel and simultaneously joined to a voice channel with the same name. The server SHALL NOT relay binary audio frames between voice channel members; it SHALL only relay WebRTC signaling messages (`voice_offer`, `voice_answer`, `voice_ice`) between named peers in the same voice channel.

#### Scenario: Voice join adds to voice members
- **WHEN** a client sends `C2S voice_join { channel: "lounge" }`
- **THEN** the client is added to the voice members of `#lounge` without affecting text channel membership

#### Scenario: Voice leave removes from voice members
- **WHEN** a client sends `C2S voice_leave { channel: "lounge" }`
- **THEN** the client is removed from the voice members of `#lounge`

#### Scenario: Disconnect cleans up voice membership
- **WHEN** a WebSocket connection closes
- **THEN** the client is removed from all voice channels they were in

#### Scenario: Server does not relay binary audio frames
- **WHEN** a binary WebSocket frame arrives from an authenticated client
- **THEN** the server SHALL drop the frame silently
- **THEN** no binary frame SHALL be forwarded to any other client

---

### Requirement: voice_state broadcast
After any voice join or voice leave the server SHALL send `S2C voice_state` to all current voice members of that channel.

#### Scenario: voice_state sent on join
- **WHEN** client A joins voice channel `#lounge` (which already has client B)
- **THEN** both client A and client B receive `S2C voice_state { channel: "lounge", users: [...] }` listing all current voice members

#### Scenario: voice_state sent on leave
- **WHEN** client A leaves voice channel `#lounge`
- **THEN** remaining voice members receive an updated `S2C voice_state` without client A

---

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

---

### Requirement: Client clears current_voice_channel on voice_state with empty users
When the client receives `S2C voice_state` for its current voice channel and the
`users` list does not contain the local user (or is empty), it SHALL clear
`current_voice_channel` to `""`.

#### Scenario: current_voice_channel clears after vleave
- **WHEN** the client sends `/vleave` and receives `S2C voice_state { users: [] }`
- **THEN** `current_voice_channel` SHALL be `""`
- **THEN** the status bar SHALL no longer show a voice-channel indicator

---

### Requirement: Active PTT or VAD stops automatically when leaving a voice channel
If the client is transmitting (PTT active) or listening (VAD mode) when
`current_voice_channel` is cleared, audio capture SHALL stop immediately.

#### Scenario: PTT stops on vleave
- **WHEN** PTT is active and the client sends `/vleave`
- **THEN** after the `voice_state` response clears `current_voice_channel`, PTT SHALL be stopped

#### Scenario: VAD listening stops on vleave
- **WHEN** VAD mode is active and the client sends `/vleave`
- **THEN** after `current_voice_channel` is cleared, `_exit_vad_listening` SHALL be called

---

### Requirement: voice_join error on non-voice channel
If a client sends `C2S voice_join` targeting a text channel or a non-existent channel, the server SHALL respond with `S2C error { code: "not_a_voice_channel" }` or `S2C error { code: "no_such_channel" }` respectively.

#### Scenario: Joining non-existent channel returns error
- **WHEN** a client sends `C2S voice_join { channel: "nope" }` and `#nope` does not exist
- **THEN** the server responds with `S2C error { code: "no_such_channel" }`

#### Scenario: Joining text channel as voice returns error
- **WHEN** a client sends `C2S voice_join { channel: "general" }` and `#general` is a text channel
- **THEN** the server responds with `S2C error { code: "not_a_voice_channel" }`
