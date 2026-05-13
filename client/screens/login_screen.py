from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from client.settings import load_settings, save_settings

LOGO = """\
  ████████╗██████╗  █████╗ ██╗  ██╗██╗   ██╗███████╗
     ██╔══╝██╔══██╗██╔══██╗╚██╗██╔╝██║   ██║██╔════╝
     ██║   ██████╔╝███████║ ╚███╔╝ ██║   ██║███████╗
     ██║   ██╔══██╗██╔══██║ ██╔██╗ ██║   ██║╚════██║
     ██║   ██║  ██║██║  ██║██╔╝ ██╗╚██████╔╝███████║
     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝\
"""


class LoginScreen(Screen):
    """Splash screen for entering server URL and username."""

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        yield Static(LOGO, id="logo")
        yield Static("Terminal chat — connect to a Traxus server", id="subtitle")
        yield Input(
            placeholder="Server URL  e.g. wss://yourname.duckdns.org",
            id="server-input",
        )
        yield Input(
            placeholder="Username",
            id="nick-input",
            max_length=32,
        )
        yield Input(
            placeholder="Password (if required by server)",
            id="password-input",
            password=True,
        )
        yield Button("Connect", id="connect-btn", variant="primary")
        yield Label("", id="error-label")

    def on_mount(self) -> None:
        settings = load_settings()
        last_server = settings.get("last_server", "")
        last_username = settings.get("last_username", "")
        if last_server:
            self.query_one("#server-input", Input).value = last_server
        if last_username:
            self.query_one("#nick-input", Input).value = last_username
        if last_server and last_username:
            self.query_one("#nick-input", Input).focus()
        else:
            self.query_one("#server-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-btn":
            self._try_connect()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "server-input":
            self.query_one("#nick-input", Input).focus()
        else:
            # Enter in nick-input or password-input both trigger connect.
            # Password is optional; don't force keyboard users through it.
            self._try_connect()

    def _try_connect(self) -> None:
        server_url = self.query_one("#server-input",   Input).value.strip()
        username   = self.query_one("#nick-input",     Input).value.strip()
        password   = self.query_one("#password-input", Input).value

        if not server_url:
            self.show_error("Please enter a server address.")
            return
        if not server_url.startswith(("ws://", "wss://")):
            server_url = "ws://" + server_url
        if not username:
            self.show_error("Please enter a username.")
            return
        if len(username) > 32 or " " in username:
            self.show_error("Username must be ≤32 chars with no spaces.")
            return

        self.show_error("")  # clear any previous error
        # Delegate to app — password is passed but never persisted.
        self.app.connect_to_server(server_url, username, password)  # type: ignore[attr-defined]
        # Persist server URL and username only (never password).
        try:
            settings = load_settings()
            settings["last_server"] = server_url
            settings["last_username"] = username
            save_settings(settings)
        except Exception:
            pass

    def show_error(self, msg: str) -> None:
        label = self.query_one("#error-label", Label)
        label.update(f"[bold #ed4245]{msg}[/bold #ed4245]" if msg else "")

    def reset_form(self) -> None:
        """Re-enable the connect button and return focus to the server URL field."""
        btn = self.query_one("#connect-btn", Button)
        btn.disabled = False
        self.query_one("#server-input", Input).focus()
