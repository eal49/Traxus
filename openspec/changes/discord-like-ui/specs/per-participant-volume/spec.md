## MODIFIED Requirements

### Requirement: MemberPanel displays per-user volume indicator for voice participants
`MemberPanel` SHALL render each user currently in a voice channel with an inline volume icon and integer percentage label. The icon tier SHALL reflect the current volume level stored in `PeerManager`: `🔇` at 0%, `🔈` at 1–50%, `🔉` at 51–149%, `🔊` at 150–200%. The percentage SHALL be displayed as a number followed by `%`.

#### Scenario: Default volume renders as 🔉 100%
- **WHEN** a voice user has not had their volume adjusted
- **THEN** their row SHALL display `🔉 100%`

#### Scenario: Icon reflects set_volume changes
- **WHEN** `set_volume("alice", 40)` is called and the panel re-renders
- **THEN** alice's row SHALL display `🔈 40%`

#### Scenario: Muted user shows 🔇 0%
- **WHEN** `set_volume("alice", 0)` is called
- **THEN** alice's row SHALL display `🔇 0%`

#### Scenario: Boosted user shows 🔊 with percentage
- **WHEN** `set_volume("alice", 160)` is called
- **THEN** alice's row SHALL display `🔊 160%`

#### Scenario: Non-voice online users have no volume indicator
- **WHEN** a member is in the Online section but not in any voice channel
- **THEN** their row SHALL NOT display a volume icon or percentage

## REMOVED Requirements

### Requirement: MemberPanel displays per-user volume bars for voice participants
**Reason**: The 10-block Unicode bargraph (`█░`) is replaced by the compact icon + percentage format (`🔇/🔈/🔉/🔊 N%`) which is less wide and still communicates the level at a glance.
**Migration**: Remove the `_volume_bar()` helper and the 10-block bar rendering from `MemberPanel`. Replace with the tiered icon lookup and `f"{icon} {level}%"` string.
