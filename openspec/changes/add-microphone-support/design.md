## Context

Traxus currently uses a single WebSocket connection per client, exchanging JSON text frames. All channels are text channels. The server stores channels in a `ChannelRegistry` dict and tracks channel membership per client inside `ConnectedClient.channels: set[str]`. The `WsWorker` send queue holds JSON strings; the recv loop iterates `async for raw in ws` and always parses `raw` as JSON.

The `websockets` library transparently yields either `str` (text frame) or `bytes` (binary frame) from the same async iterator, so the existing connection can carry audio without a second socket.

## Goals / Non-Goals

**Goals:**
- Real-time voice channels relayed over the existing WebSocket connection.
- Push-to-talk toggle (Ctrl+M) with a status bar indicator.
- Server relays raw PCM binary frames to all other voice channel members.
- Client captures mic with `sounddevice`, plays received audio with `sounddevice`.
- New slash commands: `/vcreate`, `/vjoin`, `/vleave`.

**Non-Goals:**
- Audio compression (Opus/MP3) — raw PCM only for now.
- Echo cancellation / noise suppression.
- Per-speaker volume control.
- Persistent voice channel history.
- Mobile / non-Python clients.

## Decisions

### D1 — Same WebSocket connection for audio (not a separate socket)

**Decision:** Reuse the existing WebSocket connection and send audio as binary frames.

**Rationale:** Avoids NAT/firewall complications of a second connection, no second auth handshake, and `websockets` already supports binary frames natively on the same `async for raw in ws` iterator. The bandwidth at 16 kHz mono 16-bit PCM (≈ 512 KB/s uncompressed at 16 ms frames) is acceptable on LAN.

**Alternative considered:** Separate UDP socket (RTP-style). Lower latency jitter but requires NAT traversal, a second server port, and far more implementation complexity.

---

### D2 — Binary frame format (length-prefixed header)

**Decision:** Each binary frame uses a compact header:

```
C2S audio frame:
  [1 byte: channel name length N]
  [N bytes: channel name]
  [remaining bytes: int16 LE PCM samples]

S2C audio frame:
  [1 byte: channel name length N]
  [N bytes: channel name]
  [1 byte: username length M]
  [M bytes: username (UTF-8)]
  [remaining bytes: int16 LE PCM samples]
```

**Rationale:** Minimal fixed overhead (2–64 bytes header vs. 33 % base64 expansion). Keeps audio on the fast path without JSON parsing. Server just prepends the username bytes before relaying.

**Alternative considered:** Base64-encoded PCM inside a JSON `voice_data` message. Simpler parsing but 33 % larger frames at 50 fps adds up to ~17 KB/s overhead per speaker.

**Utility:** `shared/voice_protocol.py` exposes `pack_c2s(channel, pcm_bytes)` and `unpack_s2c(frame) → (channel, username, pcm_bytes)`.

---

### D3 — Audio parameters

| Parameter | Value | Rationale |
|---|---|---|
| Sample rate | 16 000 Hz | Sufficient for voice; halves bandwidth vs. 44.1 kHz |
| Channels | 1 (mono) | Voice only; halves bandwidth vs. stereo |
| Dtype | int16 | Standard PCM; `sounddevice` default |
| Block size | 320 samples | 20 ms frames — standard VoIP frame size |

---

### D4 — Push-to-talk via Ctrl+M toggle

**Decision:** Ctrl+M cycles PTT on/off (toggle mode, not hold-to-talk).

**Rationale:** Textual's key event system fires on key-down only — there is no key-up event, so hold-to-talk is not natively supported. Toggle mode is simpler and common in software PTT implementations.

**Keybinding location:** `ChatScreen.BINDINGS` with an `action_ptt_toggle()` method that calls `app.toggle_ptt()`.

---

### D5 — sounddevice callback → asyncio queue bridge

**Decision:** The sounddevice input callback stores PCM frames in a `threading.Event`-less bridge: it calls `loop.call_soon_threadsafe(queue.put_nowait, pcm_bytes)` on the asyncio event loop reference stored in `AudioEngine`.

**Rationale:** `sounddevice` callbacks run in a C audio thread. `asyncio.Queue.put_nowait` is not thread-safe alone, but `loop.call_soon_threadsafe` safely schedules it on the asyncio loop. The async `capture_loop()` coroutine then drains the queue and calls `ws_worker.enqueue_binary()`.

---

### D6 — Voice channel membership stored server-side in ConnectionManager

**Decision:** `ConnectedClient` gains a `voice_channels: set[str]` field (alongside the existing `channels: set[str]` for text). `ConnectionManager` gains `voice_clients_in_channel(channel)` for relay targeting.

**Rationale:** Symmetric to text channel membership; minimal schema change; disconnect cleanup already iterates `client.channels` so we add a parallel loop for `client.voice_channels`.

---

### D7 — `vcreate` validates name with same regex as text channels

**Decision:** Voice channel names use the same `^[a-z0-9_-]{1,32}$` regex. They're distinguished from text channels by the `type` field in `Channel`, not by name prefix.

**Rationale:** Avoids inventing a second naming convention. The channel list UI uses a symbol (`♪` in the sidebar) rather than a name prefix to signal voice.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Raw PCM bandwidth (~512 KB/s per speaker at 16 kHz) saturates slow networks | Document LAN-only recommendation; Opus can be added later as D1 already isolates codec from transport |
| sounddevice not available on all systems (needs PortAudio) | Graceful degradation: if `import sounddevice` fails, voice commands show an error message and PTT is disabled; text channels unaffected |
| Audio thread / asyncio loop race if loop reference is stale during reconnect | Store loop reference in `AudioEngine.start()` (called after worker connects); `stop()` clears it before loop teardown |
| Textual no key-up events means no true hold-to-talk | Documented limitation; toggle mode is a known UX pattern |
| Multiple simultaneous speakers cause audio glitches with `sd.play()` | `sd.play()` overwrites previous playback; simple fix is per-speaker `OutputStream` with a mixing buffer — deferred to a follow-up change |

## Migration Plan

1. Install new deps: `pip install sounddevice numpy`.
2. Restart server — new binary frame handler is backwards compatible (old text clients send no binary frames, no change in behaviour).
3. New client connects — voice features activate only when `sounddevice` import succeeds.
4. No schema migration needed (in-memory state only).

## Open Questions

- Should `/vjoin` auto-switch the text view to a "voice channel" UI, or keep the current text view and just start audio? **Tentative: keep text view, just add audio — simpler.**
- Should the server enforce a max simultaneous voice member count per channel? **Tentative: no cap for now.**
