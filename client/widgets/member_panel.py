from __future__ import annotations

from textual import events
from textual.widget import Widget

_MIN_WIDTH = 22
_MAX_WIDTH = 40
_MEMBER_INDENT = 2
_BORDER_OVERHEAD = 1
# Columns consumed by " ▶ 🔊 " prefix and "  100%" suffix in a voice row:
#   cursor(1) + space(1) + emoji(2) + space(1) + percent_max(5) = 10 overhead
_VOICE_OVERHEAD = 10


def _clip_nick(name: str, max_len: int) -> str:
    if len(name) <= max_len:
        return name
    return (name[:max_len - 3] + "...") if max_len > 3 else name[:max_len]


def _volume_icon(level: int) -> str:
    if level == 0:
        return "🔇"
    if level <= 50:
        return "🔈"
    if level <= 149:
        return "🔉"
    return "🔊"


class MemberPanel(Widget):
    """Right-side panel showing server-wide Online / Offline member sections.

    Online users who are in a voice channel display an inline volume icon and
    percentage.  ↑/↓ navigate among voice users; ←/→ adjust their volume.
    """

    DEFAULT_CSS = ""
    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._online: list[str] = []
        self._offline: list[str] = []
        self._sorted_voice_users: list[str] = []
        self._cursor: int = 0
        self._panel_width: int = _MIN_WIDTH

    # ── Volume source: PeerManager (WebRTC) ──────────────────────────────────

    @property
    def _volume_source(self):
        try:
            return getattr(self.app, "_peer_manager", None)
        except Exception:
            return None

    # ── Width management ──────────────────────────────────────────────────────

    def _recompute_width(self) -> None:
        needed = _MIN_WIDTH
        for name in self._online + self._offline:
            needed = max(needed, len(name) + _MEMBER_INDENT)
        for name in self._sorted_voice_users:
            needed = max(needed, len(name) + _VOICE_OVERHEAD)
        self._panel_width = min(_MAX_WIDTH, needed)
        self.styles.width = self._panel_width + _BORDER_OVERHEAD

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _build_markup(self) -> str:
        max_voice_nick = max(1, self._panel_width - _VOICE_OVERHEAD)
        max_member_nick = max(1, self._panel_width - _MEMBER_INDENT)

        lines = [
            rf"[bold dim]  ONLINE — {len(self._online)}[/bold dim]"
        ]
        voice_set = set(self._sorted_voice_users)
        for name in self._online:
            if name in voice_set:
                idx = self._sorted_voice_users.index(name)
                cursor = "▶" if (idx == self._cursor and self.has_focus) else " "
                engine = self._volume_source
                level = engine.get_volume(name) if engine is not None else 100
                icon = _volume_icon(level)
                display = _clip_nick(name, max_voice_nick)
                lines.append(f" {cursor} {icon} {display}  {level}%")
            else:
                display = _clip_nick(name, max_member_nick)
                lines.append(f"  {display}")

        if self._offline:
            lines.append("")
            lines.append(
                rf"[bold dim]  OFFLINE — {len(self._offline)}[/bold dim]"
            )
            for name in self._offline:
                display = _clip_nick(name, max_member_nick)
                lines.append(f"  [dim]{display}[/dim]")

        return "\n".join(lines)

    def render(self):
        from rich.text import Text
        return Text.from_markup(self._build_markup())

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_server_members(self, online: list[str], offline: list[str]) -> None:
        self._online = list(online)
        self._offline = list(offline)
        self._recompute_width()
        self.refresh()

    def set_members(self, members: list[dict]) -> None:
        """Legacy shim: channel-scoped user_list → ignored (no-op)."""
        pass

    def update_voice(self, voice_users: list[dict]) -> None:
        self._sorted_voice_users = sorted(
            u.get("username", "") for u in voice_users if u.get("username")
        )
        self._cursor = min(self._cursor, max(0, len(self._sorted_voice_users) - 1))
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
