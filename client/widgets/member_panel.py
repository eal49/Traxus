from __future__ import annotations

from textual import events
from textual.widget import Widget

_MIN_WIDTH = 22
_MAX_WIDTH = 40
# Display columns consumed by the non-nick parts of a voice row:
#   " " cursor " " "🔊"(2) " " + "  " bar(15) = 1+1+1+2+1+2+15 = 23
_VOICE_OVERHEAD = 23
_MEMBER_INDENT = 2  # leading spaces before member name
# border-left: tall in CSS consumes 1 column from the content area;
# add this to the computed content width when setting styles.width.
_BORDER_OVERHEAD = 1


def _clip_nick(name: str, max_len: int) -> str:
    if len(name) <= max_len:
        return name
    return (name[:max_len - 3] + "...") if max_len > 3 else name[:max_len]


class MemberPanel(Widget):
    """Right-side panel showing channel members and in-voice participants.

    When focused, ↑/↓ navigate among voice users and ←/→ adjust their
    playback volume in 10% steps (0–200%, default 100%).

    Width adapts to the longest nickname (clamped to _MIN_WIDTH–_MAX_WIDTH).
    Nicknames that would overflow the max width are clipped with "…".
    """

    DEFAULT_CSS = ""
    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._members: list[dict] = []
        self._sorted_voice_users: list[str] = []
        self._cursor: int = 0
        self._panel_width: int = _MIN_WIDTH

    # ── Volume source: PeerManager (WebRTC) ──────────────────────────────────

    @property
    def _volume_source(self):
        """Return PeerManager if in a voice channel, else None."""
        try:
            return getattr(self.app, "_peer_manager", None)
        except Exception:
            return None

    # ── Width management ──────────────────────────────────────────────────────

    def _recompute_width(self) -> None:
        needed = _MIN_WIDTH
        for m in self._members:
            nick = m.get("username", "")
            needed = max(needed, len(nick) + _MEMBER_INDENT)
        for name in self._sorted_voice_users:
            needed = max(needed, len(name) + _VOICE_OVERHEAD)
        self._panel_width = min(_MAX_WIDTH, needed)
        self.styles.width = self._panel_width + _BORDER_OVERHEAD

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _volume_bar(self, username: str) -> str:
        engine = self._volume_source
        level = engine.get_volume(username) if engine is not None else 100
        filled = round(level / 20)          # 0%→0, 100%→5, 200%→10
        bar = "█" * filled + "░" * (10 - filled)
        return f"{bar} {level:3d}%"

    def _build_markup(self) -> str:
        max_voice_nick = max(1, self._panel_width - _VOICE_OVERHEAD)
        max_member_nick = max(1, self._panel_width - _MEMBER_INDENT)

        lines = [r"[bold dim]  Members[/bold dim]"]
        for m in self._members:
            name = _clip_nick(m.get("username", "?"), max_member_nick)
            lines.append(f"  {name}")

        if self._sorted_voice_users:
            lines.append("")
            lines.append(r"[bold dim]  In Voice[/bold dim]")
            for i, name in enumerate(self._sorted_voice_users):
                display = _clip_nick(name, max_voice_nick)
                cursor = "▶" if (i == self._cursor and self.has_focus) else " "
                bar = self._volume_bar(name)
                lines.append(f" {cursor} 🔊 {display}  {bar}")

        return "\n".join(lines)

    def render(self):
        from rich.text import Text
        return Text.from_markup(self._build_markup())

    # ── Public API (unchanged surface, extended) ───────────────────────────────

    def set_members(self, members: list[dict]) -> None:
        self._members = list(members)
        self._recompute_width()
        self.refresh()

    def update_voice(self, voice_users: list[dict]) -> None:
        self._sorted_voice_users = sorted(
            u.get("username", "") for u in voice_users if u.get("username")
        )
        self._cursor = 0
        self._recompute_width()
        self.refresh()

    # ── Focus / blur re-render ────────────────────────────────────────────────

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    # ── Keyboard handling ─────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if not self._sorted_voice_users:
            return
        n = len(self._sorted_voice_users)
        if event.key == "up":
            event.stop()
            self._cursor = (self._cursor - 1) % n
            self.refresh()
        elif event.key == "down":
            event.stop()
            self._cursor = (self._cursor + 1) % n
            self.refresh()
        elif event.key in ("left", "right"):
            event.stop()
            engine = self._volume_source
            if engine is None:
                return
            username = self._sorted_voice_users[self._cursor]
            delta = -10 if event.key == "left" else 10
            engine.set_volume(username, engine.get_volume(username) + delta)
            self.refresh()
