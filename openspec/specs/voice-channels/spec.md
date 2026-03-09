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
The server SHALL maintain a separate voice membership set per voice channel, independent of text channel subscriptions. A client MAY be subscribed to a text channel and simultaneously joined to a voice channel with the same name.

#### Scenario: Voice join adds to voice members
- **WHEN** a client sends `C2S voice_join { channel: "lounge" }`
- **THEN** the client is added to the voice members of `#lounge` without affecting text channel membership

#### Scenario: Voice leave removes from voice members
- **WHEN** a client sends `C2S voice_leave { channel: "lounge" }`
- **THEN** the client is removed from the voice members of `#lounge`

#### Scenario: Disconnect cleans up voice membership
- **WHEN** a WebSocket connection closes
- **THEN** the client is removed from all voice channels they were in

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

### Requirement: Binary audio frame relay
The server SHALL relay binary audio frames from a transmitting client to all other voice members of the target channel. The server SHALL NOT echo the frame back to the sender. Clients that are not voice members of that channel SHALL NOT receive the frame.

#### Scenario: Frame relayed to voice members
- **WHEN** client A (in voice channel `#lounge`) sends a binary frame with channel header `lounge`
- **THEN** all other voice members of `#lounge` receive the frame with username header prepended

#### Scenario: Non-member does not receive frame
- **WHEN** client A sends a binary frame for `#lounge`
- **THEN** client B, who is NOT a voice member of `#lounge`, does NOT receive the frame

#### Scenario: Sender does not receive own frame
- **WHEN** client A sends a binary frame
- **THEN** client A does NOT receive that same frame back

---

### Requirement: voice_join error on non-voice channel
If a client sends `C2S voice_join` targeting a text channel or a non-existent channel, the server SHALL respond with `S2C error { code: "not_a_voice_channel" }` or `S2C error { code: "no_such_channel" }` respectively.

#### Scenario: Joining non-existent channel returns error
- **WHEN** a client sends `C2S voice_join { channel: "nope" }` and `#nope` does not exist
- **THEN** the server responds with `S2C error { code: "no_such_channel" }`

#### Scenario: Joining text channel as voice returns error
- **WHEN** a client sends `C2S voice_join { channel: "general" }` and `#general` is a text channel
- **THEN** the server responds with `S2C error { code: "not_a_voice_channel" }`
