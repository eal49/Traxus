## REMOVED Requirements

### Requirement: Asyncio-safe callback bridging
**Reason**: The intermediate asyncio.Queue (`self._queue`) and `capture_loop` coroutine are eliminated. The capture callback now posts packed frames directly to the WsWorker binary send queue via `call_soon_threadsafe`. The asyncio event loop reference (`self._loop`) is still stored and used for `call_soon_threadsafe`, but the intermediate queue is gone.
**Migration**: Replace all calls to `AudioEngine.capture_loop()` with `AudioEngine.set_send_target(queue, channel)` before activating PTT, and `set_send_target(None, "")` on deactivation.

## ADDED Requirements

### Requirement: AudioEngine exposes set_send_target for direct frame posting
`AudioEngine` SHALL expose a `set_send_target(binary_send_queue, channel: str)` method. When set, the sounddevice capture callback SHALL encode, pack, and post frames directly to `binary_send_queue` via `loop.call_soon_threadsafe`. When cleared (`None`, `""`), the callback SHALL not post any frames.

#### Scenario: set_send_target registers queue and channel
- **WHEN** `set_send_target(queue, "lounge")` is called
- **THEN** `AudioEngine._send_queue` and `AudioEngine._send_channel` SHALL be set accordingly

#### Scenario: set_send_target with None clears target
- **WHEN** `set_send_target(None, "")` is called
- **THEN** the capture callback SHALL not post frames to any queue

#### Scenario: Capture callback posts directly during PTT
- **WHEN** PTT is active and a send target is configured
- **THEN** each captured frame SHALL be ADPCM-encoded, packed via `voice_protocol.pack_c2s`, and posted to `_send_queue` in a single `call_soon_threadsafe` call
