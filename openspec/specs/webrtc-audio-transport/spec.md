## Requirements

### Requirement: Client manages one RTCPeerConnection per remote voice participant
The client SHALL create and maintain one `aiortc.RTCPeerConnection` for each other participant in the active voice channel. Connections SHALL be created when a peer joins the channel and closed when they leave or disconnect.

#### Scenario: Peer connection created on voice join
- **WHEN** the local client receives a `voice_state` update adding a new participant to the voice channel
- **THEN** the client SHALL create a new `RTCPeerConnection` for that participant
- **THEN** if the local client joined after the participant, the local client SHALL send a `voice_offer` to that participant

#### Scenario: Peer connection closed on voice leave
- **WHEN** the local client receives a `voice_state` update removing a participant from the voice channel
- **THEN** the associated `RTCPeerConnection` SHALL be closed and removed from the peer map
- **THEN** playback for that participant SHALL stop immediately

#### Scenario: All connections closed on voice leave
- **WHEN** the local client sends `voice_leave`
- **THEN** ALL active `RTCPeerConnection` objects for the voice channel SHALL be closed

---

### Requirement: MicTrack bridges sounddevice capture to WebRTC
The client SHALL implement a `MicTrack` subclass of `aiortc.AudioStreamTrack` that reads 20 ms PCM frames from the sounddevice input callback and yields them as `av.AudioFrame` objects to the WebRTC pipeline.

#### Scenario: MicTrack yields frames during PTT
- **WHEN** PTT is active and the sounddevice callback fires
- **THEN** `MicTrack.recv()` SHALL yield an `av.AudioFrame` containing the 320-sample int16 PCM data
- **THEN** the frame pts SHALL be set to the frame count times the frame duration

#### Scenario: MicTrack yields silence when PTT is inactive
- **WHEN** PTT is not active
- **THEN** `MicTrack.recv()` SHALL yield an `av.AudioFrame` containing zeroed PCM samples
- **THEN** the WebRTC connection SHALL remain established (no teardown on mute)

#### Scenario: MicTrack applies noise suppression when enabled
- **WHEN** noise suppression is enabled in settings and PTT is active
- **THEN** the PCM data passed to the `av.AudioFrame` SHALL be the NS-filtered output

---

### Requirement: RemoteAudioSink bridges WebRTC receive to sounddevice playback
The client SHALL implement a `RemoteAudioSink` coroutine that reads decoded `av.AudioFrame` objects from a remote `RTCPeerConnection` audio track and writes the PCM samples to the shared `sd.OutputStream`.

#### Scenario: Remote audio frames play through OutputStream
- **WHEN** a remote `AudioStreamTrack` produces an `av.AudioFrame`
- **THEN** the decoded int16 PCM samples SHALL be written to the shared `sd.OutputStream`
- **THEN** per-participant volume gain SHALL be applied before writing

#### Scenario: Per-participant volume applies to remote track
- **WHEN** the user adjusts a participant's volume via the MemberPanel
- **THEN** the gain applied in `RemoteAudioSink` for that participant SHALL update immediately

#### Scenario: Sink stops on connection close
- **WHEN** the associated `RTCPeerConnection` closes
- **THEN** the `RemoteAudioSink` coroutine SHALL exit cleanly
- **THEN** no further audio is written to the OutputStream for that participant

---

### Requirement: ICE negotiation completes before audio flows
The client SHALL complete ICE candidate exchange before expecting audio to flow. Trickle ICE SHALL be used: candidates are sent as they are gathered rather than waiting for gathering to complete.

#### Scenario: ICE candidates sent as gathered
- **WHEN** the local ICE agent generates a candidate
- **THEN** the client SHALL immediately send a `voice_ice` signaling message to the peer
- **THEN** the client SHALL NOT wait for ICE gathering to complete before sending the offer/answer

#### Scenario: ICE connection established on LAN
- **WHEN** both peers are on the same LAN and a STUN server is reachable
- **THEN** an ICE host or peer-reflexive candidate pair SHALL be selected
- **THEN** RTP audio SHALL flow directly between clients (no server relay)

---

### Requirement: STUN server is configurable
The client SHALL use a default STUN server (`stun:stun.l.google.com:19302`) for ICE candidate gathering. The STUN server URL SHALL be overridable via `settings.json`.

#### Scenario: Default STUN server used when not configured
- **WHEN** settings.json does not contain a `stun_server` key
- **THEN** the client SHALL configure `RTCConfiguration` with `stun:stun.l.google.com:19302`

#### Scenario: Custom STUN server respected
- **WHEN** settings.json contains `{"stun_server": "stun:example.com:3478"}`
- **THEN** the client SHALL use that URL in `RTCConfiguration`
