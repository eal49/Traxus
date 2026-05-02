## Why

`/vleave` silently fails when other users are still in the voice channel: the server sends the leaving client the remaining-members roster, the client sees a non-empty `users` list, keeps `current_voice_channel` set, and never tears down the WebRTC peer connections. The bug only disappears when the leaving user is last — a corner case that masked it until now.

## What Changes

- **Server** (`server/message_router.py`): `_handle_voice_leave` sends the leaving client an empty `users` list so the client knows it has departed, regardless of how many participants remain.
- **Client** (`client/app.py`): the `voice_state` handler passes `self.current_voice_channel` (the post-update reactive value) instead of the raw payload `channel` to `_handle_voice_state_webrtc`, so `left_voice` is computed correctly.
- **Tests**: new cases covering `/vleave` with one or more remaining participants; existing tests updated to match the corrected server behaviour.

## Capabilities

### New Capabilities

*(none — this is a bug fix)*

### Modified Capabilities

- `vleave-command`: the leaving client now reliably receives an empty-users voice_state, clearing its channel state and closing WebRTC connections regardless of remaining participants.

## Impact

- `server/message_router.py` — one-line change in `_handle_voice_leave`
- `client/app.py` — one-argument change in the `voice_state` handler
- `tests/test_message_router.py` — add/update vleave tests
- `tests/test_app.py` — add vleave-with-remaining-users test
