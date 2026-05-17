# opus-codec-params Specification

## Purpose
TBD - created by archiving change opus-bandwidth-optimisation. Update Purpose after archive.
## Requirements
### Requirement: Opus codec parameters are negotiated via SDP fmtp injection
The client SHALL inject Opus-specific parameters into the `a=fmtp` line of every outgoing SDP offer and answer before calling `setLocalDescription`. Injected parameters SHALL include DTX enablement, in-band FEC enablement, and a maximum average bitrate cap. If the SDP already contains an `a=fmtp` line for the Opus payload type, the parameters SHALL be merged with any existing parameters (existing parameters preserved, new parameters added or overwritten). If no `a=fmtp` line exists, one SHALL be inserted immediately after the corresponding `a=rtpmap` line.

#### Scenario: DTX enabled in outgoing offer
- **WHEN** `connect()` creates an outgoing offer for a remote participant
- **THEN** the SDP passed to `setLocalDescription` SHALL contain `usedtx=1` in the Opus fmtp line

#### Scenario: FEC enabled in outgoing offer
- **WHEN** `connect()` creates an outgoing offer for a remote participant
- **THEN** the SDP passed to `setLocalDescription` SHALL contain `useinbandfec=1` in the Opus fmtp line

#### Scenario: Bitrate cap applied in outgoing offer
- **WHEN** `connect()` creates an outgoing offer for a remote participant
- **THEN** the SDP passed to `setLocalDescription` SHALL contain `maxaveragebitrate=16000` in the Opus fmtp line

#### Scenario: Parameters applied to answer SDP
- **WHEN** `on_offer()` creates an answer in response to a remote offer
- **THEN** the SDP passed to `setLocalDescription` SHALL contain `usedtx=1`, `useinbandfec=1`, and `maxaveragebitrate=16000` in the Opus fmtp line

#### Scenario: Existing fmtp parameters are preserved on merge
- **WHEN** the SDP produced by `createOffer` or `createAnswer` already contains Opus fmtp parameters (e.g. `minptime=10`)
- **THEN** those parameters SHALL be retained in the patched SDP alongside the injected parameters

#### Scenario: fmtp line inserted when absent
- **WHEN** the SDP produced by `createOffer` or `createAnswer` has no `a=fmtp` line for the Opus payload type
- **THEN** the patched SDP SHALL contain a new `a=fmtp` line placed immediately after the `a=rtpmap` line for Opus

#### Scenario: Non-Opus SDP left unchanged
- **WHEN** the SDP contains no Opus `a=rtpmap` line
- **THEN** `_patch_opus_sdp` SHALL return the SDP string unmodified

