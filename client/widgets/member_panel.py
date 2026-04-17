from __future__ import annotations

from textual import events
from textual.widget import Widget


class MemberPanel(Widget):
    """Right-side panel showing channel members and in-voice participants.

    When focused, ↑/↓ navigate among voice users and ←/→ adjust their
    playback volume in 10% steps (0–200%, default 100%).
    """

    DEFAULT_CSS = ""
    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._members: list[dict] = []
        self._sorted_voice_users: list[str] = []
        self._cursor: int = 0

    # ── AudioEngine access (same pattern as SettingsScreen) ───────────────────

    @property
    def _audio_engine(self):
        return getattr(self.app, "_audio_engine", None)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _volume_bar(self, username: str) -> str:
        engine = self._audio_engine
        level = engine.get_volume(username) if engine is not None else 100
        filled = round(level / 20)          # 0%→0, 100%→5, 200%→10
        bar = "█" * filled + "░" * (10 - filled)
        return f"{bar} {level:3d}%"

    def _build_markup(self) -> str:
        lines = [r"[bold dim]  Members[/bold dim]"]
        for m in self._members:
            name = m.get("username", "?")
            lines.append(f"  {name}")

        if self._sorted_voice_users:
            lines.append("")
            lines.append(r"[bold dim]  In Voice[/bold dim]")
            for i, name in enumerate(self._sorted_voice_users):
                cursor = "▶" if (i == self._cursor and self.has_focus) else " "
                bar = self._volume_bar(name)
                lines.append(f" {cursor} 🔊 {name}  {bar}")

        return "\n".join(lines)

    def render(self):
        from rich.text import Text
        return Text.from_markup(self._build_markup())

    # ── Public API (unchanged surface, extended) ───────────────────────────────

    def set_members(self, members: list[dict]) -> None:
        self._members = list(members)
        self.refresh()

    def update_voice(self, voice_users: list[dict]) -> None:
        self._sorted_voice_users = sorted(
            u.get("username", "") for u in voice_users if u.get("username")
        )
        self._cursor = 0
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
            engine = self._audio_engine
            if engine is None:
                return
            username = self._sorted_voice_users[self._cursor]
            delta = -10 if event.key == "left" else 10
            engine.set_volume(username, engine.get_volume(username) + delta)
            self.refresh()
