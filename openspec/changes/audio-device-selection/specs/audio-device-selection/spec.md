## ADDED Requirements

### Requirement: User can select input and output audio devices
The client SHALL allow the user to independently select the microphone input device and speaker output device from a list of available system devices. The selection SHALL be persisted in `settings.json` and restored on next launch.

#### Scenario: Saved input device is used on next voice channel join
- **WHEN** `input_device` is set to a non-null device name in `settings.json`
- **THEN** `MicTrack` SHALL open its `sd.InputStream` with `device=<name>` rather than the system default

#### Scenario: Saved output device is used on next voice channel join
- **WHEN** `output_device` is set to a non-null device name in `settings.json`
- **THEN** the `sd.OutputStream` opened on `/vjoin` SHALL use `device=<name>` rather than the system default

#### Scenario: System Default means no device argument
- **WHEN** `input_device` or `output_device` is `null` (or absent) in `settings.json`
- **THEN** the corresponding stream SHALL be opened without a `device=` argument, using the OS default

#### Scenario: Unavailable saved device falls back to system default
- **WHEN** the saved device name is not found by sounddevice at stream open time
- **THEN** the stream SHALL open on the system default device
- **THEN** a warning SHALL be displayed in the chat area

---

### Requirement: Device selection hot-swaps while in a voice channel
Changing the input or output device while in a voice channel SHALL take effect immediately without requiring the user to leave and rejoin.

#### Scenario: Input device change restarts MicTrack stream
- **WHEN** the user selects a new input device from Settings while in a voice channel
- **THEN** `MicTrack.restart_stream(new_device)` SHALL be called
- **THEN** the aiortc track and all existing peer connections SHALL remain intact

#### Scenario: Output device change hot-swaps OutputStream
- **WHEN** the user selects a new output device from Settings while in a voice channel
- **THEN** `PeerManager.restart_output_stream(new_device)` SHALL be called
- **THEN** running `RemoteAudioSink` tasks SHALL write to the new stream on the next frame without being cancelled

#### Scenario: Device change outside voice channel takes effect on next join
- **WHEN** the user changes a device while NOT in a voice channel
- **THEN** the new device SHALL be saved to settings
- **THEN** it SHALL be used when the user next runs `/vjoin`

---

### Requirement: DeviceSelectScreen presents available devices
The `DeviceSelectScreen` modal SHALL enumerate available audio devices using `sd.query_devices()` and present them in a navigable list. "System Default" SHALL always be the first entry.

#### Scenario: Input device screen lists only input-capable devices
- **WHEN** `DeviceSelectScreen` is opened with `kind="input"`
- **THEN** only devices with `max_input_channels > 0` SHALL be listed (plus System Default)

#### Scenario: Output device screen lists only output-capable devices
- **WHEN** `DeviceSelectScreen` is opened with `kind="output"`
- **THEN** only devices with `max_output_channels > 0` SHALL be listed (plus System Default)

#### Scenario: Selecting System Default clears saved device
- **WHEN** the user selects "System Default" in the device picker
- **THEN** the corresponding `settings.json` key SHALL be set to `null`

#### Scenario: Selecting a named device saves the device name
- **WHEN** the user selects a named device in the picker
- **THEN** the device name string SHALL be saved to `settings.json`

#### Scenario: Escape cancels without saving
- **WHEN** the user presses Escape in the device picker
- **THEN** no change SHALL be made to the saved settings

---

### Requirement: MicTestScreen uses the selected input device
`MicTestScreen` SHALL open the microphone on the user-selected input device.

#### Scenario: MicTestScreen uses saved input device
- **WHEN** `MicTestScreen` opens and `app._input_device` is set
- **THEN** `AudioEngine.start_vad()` SHALL be called with `device=app._input_device`

#### Scenario: MicTestScreen uses system default when no device saved
- **WHEN** `MicTestScreen` opens and `app._input_device` is `None`
- **THEN** `AudioEngine.start_vad()` SHALL be called with `device=None`
