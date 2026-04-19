## Requirements

### Requirement: Server relays SDP offer messages between named peers
The server SHALL relay `voice_offer` C2S messages to the named target user in the same voice channel. The server SHALL set `from_user` to the sender's authenticated username before forwarding.

#### Scenario: Offer delivered to target in same voice channel
- **WHEN** a client sends `{type: "voice_offer", to_user: "bob", sdp: "..."}`
- **THEN** the server SHALL deliver `{type: "voice_offer", from_user: "alice", to_user: "bob", sdp: "..."}` to bob's WebSocket
- **THEN** the server SHALL NOT broadcast the offer to other channel members

#### Scenario: Offer rejected if target not in same voice channel
- **WHEN** a client sends `voice_offer` to a user who is not in the same voice channel
- **THEN** the server SHALL silently drop the message
- **THEN** no error is returned to the sender

#### Scenario: Server overwrites from_user field
- **WHEN** a client sends `voice_offer` with a spoofed `from_user` field
- **THEN** the server SHALL replace `from_user` with the authenticated username of the connection

---

### Requirement: Server relays SDP answer messages between named peers
The server SHALL relay `voice_answer` C2S messages to the named target user identically to offer relay.

#### Scenario: Answer delivered to target
- **WHEN** a client sends `{type: "voice_answer", to_user: "alice", sdp: "..."}`
- **THEN** the server SHALL deliver it to alice's WebSocket with `from_user` set to the sender

#### Scenario: Answer dropped if target absent
- **WHEN** the target user has disconnected between offer and answer
- **THEN** the server SHALL silently drop the answer message

---

### Requirement: Server relays ICE candidate messages between named peers
The server SHALL relay `voice_ice` C2S messages to the named target user. The message payload includes `candidate`, `sdpMid`, and `sdpMLineIndex`.

#### Scenario: ICE candidate delivered to target
- **WHEN** a client sends `{type: "voice_ice", to_user: "bob", candidate: "...", sdpMid: "0", sdpMLineIndex: 0}`
- **THEN** the server SHALL deliver the message to bob with `from_user` set

#### Scenario: End-of-candidates signal relayed
- **WHEN** a client sends `voice_ice` with `candidate: null` (end-of-candidates)
- **THEN** the server SHALL relay it unchanged to the target

---

### Requirement: Signaling messages are JSON text frames on the existing WebSocket
All three signaling message types (`voice_offer`, `voice_answer`, `voice_ice`) SHALL be sent as UTF-8 JSON text frames on the existing WebSocket connection, not as binary frames.

#### Scenario: Signaling messages use text WebSocket frames
- **WHEN** a client sends a `voice_offer` signaling message
- **THEN** the WebSocket frame type SHALL be text (not binary)
- **THEN** the message SHALL be a valid JSON object with a `type` field

#### Scenario: Client uses existing WsWorker text queue for signaling
- **WHEN** the client initiates a WebRTC offer
- **THEN** the JSON-serialized offer SHALL be enqueued via `WsWorker.enqueue()` (the text send queue)
- **THEN** no binary WebSocket frames SHALL be used for signaling

---

### Requirement: New signaling message types added to shared constants
`shared/message_types.py` SHALL define constants for the six new message types: `C2S.VOICE_OFFER`, `C2S.VOICE_ANSWER`, `C2S.VOICE_ICE`, `S2C.VOICE_OFFER`, `S2C.VOICE_ANSWER`, `S2C.VOICE_ICE`.

#### Scenario: Constants available in shared module
- **WHEN** server or client code imports `from shared.message_types import C2S, S2C`
- **THEN** `C2S.VOICE_OFFER`, `C2S.VOICE_ANSWER`, `C2S.VOICE_ICE` SHALL be accessible string constants
- **THEN** `S2C.VOICE_OFFER`, `S2C.VOICE_ANSWER`, `S2C.VOICE_ICE` SHALL be accessible string constants
