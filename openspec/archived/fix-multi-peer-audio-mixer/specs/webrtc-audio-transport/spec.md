## MODIFIED Requirements

### Requirement: RemoteAudioSink bridges WebRTC receive to sounddevice playback
The client SHALL implement a `RemoteAudioSink` coroutine that reads decoded `av.AudioFrame` objects from a remote `RTCPeerConnection` audio track, applies per-participant volume gain, and pushes the resulting int16 PCM to the shared `AudioMixer` via `mixer.push(username, pcm)`. `RemoteAudioSink` SHALL NOT write to `sd.OutputStream` directly.

#### Scenario: Remote audio frames are pushed to the AudioMixer
- **WHEN** a remote `AudioStreamTrack` produces an `av.AudioFrame`
- **THEN** the decoded int16 PCM samples SHALL be pushed to `AudioMixer` for that participant
- **THEN** per-participant volume gain SHALL be applied before pushing

#### Scenario: Per-participant volume applies to remote track
- **WHEN** the user adjusts a participant's volume via the MemberPanel
- **THEN** the gain applied in `RemoteAudioSink` for that participant SHALL update immediately on the next frame

#### Scenario: Sink stops on connection close
- **WHEN** the associated `RTCPeerConnection` closes
- **THEN** the `RemoteAudioSink` coroutine SHALL exit cleanly
- **THEN** no further frames are pushed to the AudioMixer for that participant
