from __future__ import annotations

from textual.widgets import Static


class MemberPanel(Static):
    """Right-side panel showing members of the active text channel."""

    DEFAULT_CSS = ""

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._members: list[dict] = []
        self._voice_users: set[str] = set()

    def _build_markup(self) -> str:
        lines = [r"[bold dim]  Members[/bold dim]"]
        for m in self._members:
            name = m.get("username", "?")
            if name in self._voice_users:
                lines.append(f"  🎤 {name}")
            else:
                lines.append(f"  {name}")
        return "\n".join(lines)

    def set_members(self, members: list[dict]) -> None:
        self._members = list(members)
        self.update(self._build_markup())

    def update_voice(self, voice_users: list[dict]) -> None:
        self._voice_users = {u.get("username", "") for u in voice_users}
        self.update(self._build_markup())
