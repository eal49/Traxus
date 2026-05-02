## 1. Server Fix

- [x] 1.1 In `server/message_router.py` `_handle_voice_leave`: replace the final `await self._conn.send_to(client.user_id, voice_state)` with a send that uses `users=[]` — so the leaving client always receives an empty roster: `{"type": S2C.VOICE_STATE, "channel": channel, "users": []}`

## 2. Client Fix

- [x] 2.1 In `client/app.py` `on_traxus_app_server_message`, `voice_state` case: change the `loop.create_task(self._handle_voice_state_webrtc(channel, users, prev_channel))` call to pass `self.current_voice_channel` instead of `channel` as the first argument, so `left_voice` is computed from the post-update reactive value rather than the raw payload

## 3. Tests

- [x] 3.1 In `tests/test_message_router.py`: add a test asserting that when Alice leaves while Bob remains, Alice receives `voice_state` with `users=[]` and Bob receives `voice_state` with `users=[bob]`
- [x] 3.2 In `tests/test_app.py`: add a test to `TestVleaveClientBehaviour` asserting that receiving `voice_state { channel: "lounge", users: [] }` while `current_voice_channel == "lounge"` correctly closes the PeerManager (mock `_peer_manager.close_all` as AsyncMock and assert it is awaited)

## 4. Verification

- [x] 4.1 Run the full test suite (`python -m unittest discover -s tests -v`) and confirm all tests pass
