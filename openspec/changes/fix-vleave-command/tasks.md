## 1. Server fix

- [x] 1.1 In `server/message_router.py` `_handle_voice_leave`, after the broadcast loop, add `await self._conn.send_to(client.user_id, voice_state)` to notify the leaving client

## 2. Client fix

- [x] 2.1 In `client/app.py` `watch_current_voice_channel`, when `name` is `""` (channel cleared), call `stop_ptt()` if PTT is active and `_exit_vad_listening()` if VAD mode is active

## 3. Tests

- [x] 3.1 In `tests/test_message_router.py`, add a test verifying that `_handle_voice_leave` sends `voice_state` to the leaving client
- [x] 3.2 In `tests/test_app.py`, add a test verifying that receiving `voice_state` with no users clears `current_voice_channel`
- [x] 3.3 In `tests/test_app.py`, add a test verifying that active PTT is stopped when `current_voice_channel` is cleared via `voice_state`
- [x] 3.4 Run full test suite and confirm all tests pass
