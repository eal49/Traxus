## 1. Shared protocol

- [ ] 1.1 Add `VOICE_JOIN`, `VOICE_LEAVE` to `C2S` class and `VOICE_STATE` to `S2C` class in `shared/message_types.py`
- [ ] 1.2 Add `NOT_A_VOICE_CHANNEL` to `ErrorCode` in `shared/message_types.py`
- [ ] 1.3 Create `shared/voice_protocol.py` with `pack_c2s(channel, pcm_bytes) → bytes` and `unpack_s2c(frame) → (channel, username, pcm_bytes)` using the length-prefixed binary frame format

## 2. Server — channel model

- [ ] 2.1 Add `type: str = "text"` field to the `Channel` dataclass in `server/channel_registry.py`
- [ ] 2.2 Add `vcreate(name, topic, created_by)` method to `ChannelRegistry` that creates a channel with `type="voice"`
- [ ] 2.3 Add `channel_summary()` to include `type` in the dict returned (so `channel_list` carries type info)

## 3. Server — connection manager

- [ ] 3.1 Add `voice_channels: set[str]` field to the `ConnectedClient` dataclass (default empty set)
- [ ] 3.2 Add `voice_clients_in_channel(channel) → list[ConnectedClient]` method to `ConnectionManager`

## 4. Server — message router

- [ ] 4.1 Add `_handle_voice_join` handler: validate channel exists and is voice type, add to `client.voice_channels`, send `voice_state` to all current voice members
- [ ] 4.2 Add `_handle_voice_leave` handler: remove from `client.voice_channels`, send updated `voice_state` to remaining voice members
- [ ] 4.3 Add `relay_voice(frame: bytes, ws, client)` method: parse channel header from binary frame, relay to all other voice members with username prepended (using `voice_protocol`)
- [ ] 4.4 Register `C2S.VOICE_JOIN` and `C2S.VOICE_LEAVE` in the `_handlers` dispatch table
- [ ] 4.5 Update `on_disconnect` to also remove the client from all `voice_channels` they were in

## 5. Server — main entry point

- [ ] 5.1 Update `client_handler` in `server/main.py` to check `isinstance(raw, bytes)` before JSON dispatch; call `await router.relay_voice(raw, ws, client)` for binary frames

## 6. Client — WsWorker

- [ ] 6.1 Add `enqueue_binary(data: bytes)` method to `WsWorker` that puts raw bytes onto a new `_binary_send_queue: asyncio.Queue[bytes]`
- [ ] 6.2 Update `_send_loop` to drain both `_send_queue` (JSON text) and `_binary_send_queue` (binary) using `asyncio.wait` or a merged coroutine
- [ ] 6.3 Update `_recv_loop` to detect `isinstance(raw, bytes)` and post `TraxusApp.AudioFrame(raw)` to the app instead of parsing as JSON

## 7. Client — audio engine

- [ ] 7.1 Create `client/audio_engine.py` with `AudioEngine` class
- [ ] 7.2 Implement `AudioEngine.start(loop)` — store the asyncio loop reference and open a `sounddevice.InputStream` with params `samplerate=16000, channels=1, dtype='int16', blocksize=320`
- [ ] 7.3 Implement the sounddevice input callback: call `loop.call_soon_threadsafe(queue.put_nowait, indata.tobytes())` when `self._transmitting` is True
- [ ] 7.4 Implement `AudioEngine.capture_loop(channel, send_fn)` async method: drain the PCM queue and call `await send_fn(channel, pcm_bytes)` for each frame
- [ ] 7.5 Implement `AudioEngine.play(pcm_bytes)`: call `sounddevice.play(np.frombuffer(pcm_bytes, dtype=np.int16), samplerate=16000, blocking=False)`
- [ ] 7.6 Implement `AudioEngine.stop()` — clear loop reference, stop the InputStream
- [ ] 7.7 Wrap the entire `AudioEngine` in a try/except `ImportError` guard at module level; set `AUDIO_AVAILABLE = False` when sounddevice or numpy are missing

## 8. Client — app integration

- [ ] 8.1 Add `TraxusApp.AudioFrame(Message)` inner class with a `data: bytes` field
- [ ] 8.2 Add `on_traxus_app_audio_frame` handler in `TraxusApp`: decode with `voice_protocol.unpack_s2c()` and call `audio_engine.play(pcm_bytes)`
- [ ] 8.3 Add `toggle_ptt()` method to `TraxusApp`: if not in a voice channel show hint, else toggle `_transmitting`; start/stop capture loop worker accordingly
- [ ] 8.4 Update `_execute_command` for new commands: `vjoin`, `vleave`, `vcreate` (guard each with `AUDIO_AVAILABLE` check for vjoin/vleave)
- [ ] 8.5 Add `current_voice_channel: reactive[str]` to `TraxusApp` (empty string when not in voice)
- [ ] 8.6 Handle `S2C.VOICE_STATE` in `on_traxus_app_server_message`: update `current_voice_channel` and pass user list to a new `ChatScreen.update_voice_state()` method

## 9. Client — commands

- [ ] 9.1 Add `vjoin`, `vleave`, `vcreate` to `KNOWN_COMMANDS` in `client/commands.py`
- [ ] 9.2 Update `HELP_TEXT` to include the three new voice commands and the Ctrl+M PTT keybinding

## 10. Client — UI widgets

- [ ] 10.1 Update `ChannelSidebar.refresh_channels()` to render voice channels with `♪ ` prefix instead of `# ` prefix
- [ ] 10.2 Add `ptt_active: reactive[bool]` to `StatusBar`; update `render()` to append `[bold red] ● MIC[/bold red]` when true
- [ ] 10.3 Add `update_ptt(active: bool)` method to `StatusBar` and wire it from `TraxusApp.toggle_ptt()`
- [ ] 10.4 Add `update_voice_state(users: list[dict])` method to `ChatScreen` (shows voice member list in sidebar or a new panel — minimum viable: a system message listing who is in voice)
- [ ] 10.5 Add `BINDINGS = [("ctrl+m", "ptt_toggle", "PTT Toggle")]` to `ChatScreen` and implement `action_ptt_toggle()` calling `self.app.toggle_ptt()`

## 11. Dependencies

- [ ] 11.1 Add `sounddevice>=0.4` and `numpy>=1.26` to `requirements.txt`
- [ ] 11.2 Install new deps: `python -m pip install sounddevice numpy`

## 12. Tests

- [ ] 12.1 Add `tests/test_voice_protocol.py` — unit tests for `pack_c2s` / `unpack_s2c` round-trip, channel header parsing edge cases
- [ ] 12.2 Add server tests in `tests/test_message_router.py`: `voice_join` success, `voice_join` on text channel returns `not_a_voice_channel`, `voice_join` on missing channel returns `no_such_channel`, `voice_leave` success, `on_disconnect` clears voice channels
- [ ] 12.3 Add `test_relay_voice` in `tests/test_message_router.py`: binary frame is relayed to other voice members, not echoed to sender, not sent to non-members
- [ ] 12.4 Add `test_binary_frame_routing` in `tests/test_app.py`: `AudioFrame` message dispatches to `audio_engine.play()` (mock AudioEngine)

## 13. Documentation

- [ ] 13.1 Update `docs/commands.md` — add `/vjoin`, `/vleave`, `/vcreate` entries and Ctrl+M PTT note
- [ ] 13.2 Update `docs/protocol.md` — add binary frame transport note, `voice_join`/`voice_leave` C2S sections, `voice_state` S2C section, `not_a_voice_channel` error code
- [ ] 13.3 Update `docs/server-rules.md` — voice channel type validation, broadcast scope entries for `voice_state` and binary frames, disconnect cleanup update
