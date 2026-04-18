## Context

`MessageView` is a subclass of Textual's `RichLog` widget. It stores rendered markup strings in `_lines: list[str]` but carries no structured message data. The server currently sends chat payloads with `type`, `username`, `content`, `ts`, and `channel` — no stable message identifier exists anywhere in the protocol.

The input bar (`InputBar`) is a plain Textual `Input` widget. Slash commands are parsed in `client/commands.py` via `parse_input()` after the user presses Enter. There is currently no mechanism for mid-input cursor handoff to another widget.

## Goals / Non-Goals

**Goals:**
- Add `msg_id` to every outgoing server chat message (UUID4, generated at relay time)
- Allow `/quote ` and `/pin ` typed in InputBar to activate a line-selection cursor in MessageView without leaving the keyboard
- `/quote`: populate InputBar with `> @nick: content` on line selection
- `/pin`: send pin request to server; server broadcasts; MessageView shows a sticky pin header
- Pinned messages survive channel rejoin (stored in `ChannelRegistry`, sent in join response)

**Non-Goals:**
- Multiple simultaneous pins (one pin per channel for now — simplest useful scope)
- Editing or deleting messages
- Persistent pin storage across server restart (in-memory only)
- Rich-text rendering inside the quoted string (IRC-style plain text only)
- Mobile/mouse-click selection

## Decisions

### D1: msg_id generated at relay, not at send

**Decision:** The server assigns `msg_id = str(uuid4())` when relaying a message to the channel (in `MessageRouter._handle_message`), not when the client sends it.

**Rationale:** Clients are untrusted; a server-assigned ID is authoritative and deduplication-safe. No protocol change needed on the C2S side.

**Alternative considered:** Client-generated UUIDs sent with every message. Rejected: adds C2S complexity, requires validation, client could forge IDs.

### D2: Augment RichLog (Option A) — parallel payload store

**Decision:** Keep `MessageView(RichLog)` and add `_payloads: list[dict | None]` in lockstep with `_lines`. Cursor rendering triggers a full `clear()` + rewrite of all lines (same pattern already used on resize).

**Rationale:** Replacing `RichLog` with a custom scroll widget is a large rewrite with many edge cases (scroll anchoring, mouse events, Textual lifecycle). The parallel store approach is surgical and testable in isolation. Full rewrite on cursor move is acceptable — `RichLog` already does it on resize and the list is capped by history limit.

**Alternative considered:** Replace `RichLog` with a custom `ListView`-based widget. Rejected: high implementation cost, loss of RichLog scroll/search behaviour.

### D3: Cursor activation via InputBar content watching

**Decision:** `InputBar` watches its own `Input.Changed` event. When the current value matches the regex `^/(quote|pin)\s$` (exactly the command word + one space, no further text), it posts a custom `SelectionModeRequested(command)` message to the app and clears the input. The app puts `MessageView` into selection mode.

**Rationale:** The space after the command word is a natural, intentional delimiter — users already expect slash commands to be followed by arguments. Watching for exactly one trailing space means the user typed the command and pressed space, signalling intent to pick a target. No separate keybinding is needed.

**Alternative considered:** Dedicated keybinding to enter selection mode (e.g., Ctrl+Up). Rejected: harder to discover; the slash-command affordance is already established in this app.

### D4: One pin per channel

**Decision:** `ChannelRegistry` stores `_pins: dict[str, str]` — one `msg_id` per channel (not a list). Pinning a new message replaces the existing pin. The server broadcasts `S2C.PIN_REPLACED` (carries old and new msg_id) rather than separate add/remove.

**Rationale:** Multiple pins require a pin management UI (reordering, removing individual pins). One pin is immediately useful and keeps the protocol and UI simple.

**Alternative considered:** Ordered list of pins. Rejected: scope creep; deferred.

### D5: Pin header rendered above message history in ChatScreen

**Decision:** `ChatScreen` composes a `Static` widget (`#pin-header`) above `MessageView`. When a `pin_added` / `pin_replaced` server message arrives, the app updates the pin payload and calls `ChatScreen.update_pin(payload | None)`. `update_pin` re-renders the static with `> @nick: content` (same IRC style as quote).

**Rationale:** Keeping the pin display in `ChatScreen` (not inside `MessageView`) avoids scroll-position coupling. The header is outside the scrollable area, so it truly stays "pinned" regardless of scroll position.

## Risks / Trade-offs

- **Full redraw on every cursor move**: For channels with long histories (500+ messages), the clear+rewrite loop will briefly flicker. Mitigation: history is already capped at 500 messages server-side; in practice the redraw is imperceptible.
- **msg_id not backfilled in history**: Messages already in `ChannelRegistry.history` before this change are delivered without `msg_id`. Pinning them is impossible. Mitigation: `_payloads` entry is `None` for legacy messages; cursor skips `None` entries for pin (can still quote them since content is in the markup).
- **Race condition on pin**: Two clients pin simultaneously — last write wins at server. Mitigation: server processes serially (asyncio single-threaded); no locking needed.
- **InputBar cleared on command detection**: If the user types `/pin ` by accident and immediately presses Backspace, the command has already been consumed and the input cleared. Mitigation: Escape exits selection mode cleanly with no state change; the user loses only the partial input, which is recoverable by retyping.

## Migration Plan

Protocol change is additive: `msg_id` is a new optional field on `S2C.MESSAGE`. Older clients that do not read `msg_id` will silently ignore it — no breaking change. Pin messages are new message types; old clients will receive unknown-type payloads (currently dropped silently by `app.on_traxus_app_server_message`'s match statement default).

No persistent state is introduced; server restart clears all pins. No migration script required.
