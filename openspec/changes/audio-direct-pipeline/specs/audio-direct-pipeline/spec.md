## ADDED Requirements

### Requirement: Audio receive path bypasses Textual message bus
When a binary WebSocket frame arrives in the WsWorker receive loop, the audio payload SHALL be decoded and passed directly to `AudioEngine.play()` without posting any message through Textual's internal message bus.

#### Scenario: Binary frame played without Textual involvement
- **WHEN** a binary audio frame arrives in `WsWorker._recv_loop`
- **THEN** `AudioEngine.play()` SHALL be called directly within `_recv_loop`
- **THEN** no Textual `Message` subclass SHALL be posted for the audio frame

#### Scenario: Malformed binary frame does not crash recv loop
- **WHEN** a binary frame arrives that cannot be unpacked by `voice_protocol.unpack_s2c`
- **THEN** the exception SHALL be silently caught
- **THEN** `_recv_loop` SHALL continue processing subsequent frames

### Requirement: Audio send path uses single asyncio hop
The audio capture callback SHALL post fully packed audio frames directly to the WsWorker binary send queue via `loop.call_soon_threadsafe`, eliminating any intermediate asyncio queue or coroutine between the capture callback and the WebSocket send loop.

#### Scenario: Packed frame reaches send queue in one hop
- **WHEN** the sounddevice capture callback fires during PTT transmission
- **THEN** the ADPCM-encoded, protocol-packed frame SHALL be posted to `_binary_send_queue` via a single `call_soon_threadsafe` call
- **THEN** no intermediate asyncio.Queue or coroutine SHALL be involved in the send path

#### Scenario: Capture callback does not block
- **WHEN** the capture callback posts a frame via `call_soon_threadsafe`
- **THEN** the callback SHALL return within the 20 ms audio callback budget without blocking

### Requirement: Audio send target is configured before PTT activation
Before the sounddevice capture callback can post frames, a send target SHALL be registered on `AudioEngine` via `set_send_target(binary_send_queue, channel)`. On PTT deactivation or voice channel leave, the send target SHALL be cleared via `set_send_target(None, "")`.

#### Scenario: Frames posted only when send target is set
- **WHEN** `set_send_target` has been called with a valid queue and channel
- **THEN** captured frames SHALL be posted to that queue during PTT transmission

#### Scenario: No frames posted when send target is cleared
- **WHEN** `set_send_target(None, "")` has been called
- **THEN** captured frames SHALL NOT be posted to any queue

### Requirement: Server relays audio frames concurrently to all receivers
The server SHALL send audio frames to all voice channel members concurrently, not sequentially.

#### Scenario: Multiple receivers get frames in parallel
- **WHEN** a voice frame arrives and there are N receivers in the channel
- **THEN** all N `ws.send()` calls SHALL be initiated concurrently via `asyncio.gather`

#### Scenario: Failed send to one receiver does not block others
- **WHEN** one receiver's WebSocket raises an exception during relay
- **THEN** frames SHALL still be sent to all other receivers
