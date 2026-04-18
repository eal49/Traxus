## What's new

- **Direct audio pipeline** — bypasses the Textual message pump for all audio
  frames, eliminating 0–50 ms of variable latency per received frame. Incoming
  voice frames are now decoded and queued directly in the WebSocket recv loop
  instead of going through Textual's event bus.
- **Single-hop send path** — microphone capture posts directly to the WebSocket
  binary queue via `call_soon_threadsafe`, removing three asyncio context
  switches from the transmit path.
- **Concurrent server relay** — the server now relays voice frames to all
  receivers in parallel (`asyncio.gather`) instead of sequentially, so one slow
  client cannot delay audio delivery to others.
- **LAN latency** — median end-to-end pipeline latency measured at ~3–4 ms
  under loopback/LAN conditions (new `test_audio_pipeline_latency.py`).

## Bug fixes

- Fixed missing `asyncio` import in `server/message_router.py` that caused a
  `NameError` crash when the concurrent relay was first invoked.

## Breaking changes

- None.
