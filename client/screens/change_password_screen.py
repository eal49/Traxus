"""
ChangePasswordScreen — modal for self-service password change.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from shared.message_types import C2S, PasswordChangeError

_ERROR_MESSAGES = {
    PasswordChangeError.WRONG_PASSWORD: "Current password is incorrect.",
    PasswordChangeError.TOO_SHORT:      "New password must be at least 10 characters.",
    PasswordChangeError.SAME_PASSWORD:  "New password must differ from current password.",
    PasswordChangeError.AUTH_DISABLED:  "Password authentication is not enabled on this server.",
}


class ChangePasswordScreen(ModalScreen[None]):
    """Modal screen for changing the user's password."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    ChangePasswordScreen {
        align: center middle;
    }
    ChangePasswordScreen > #dialog {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 1 2;
    }
    ChangePasswordScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    ChangePasswordScreen Input {
        margin-bottom: 1;
    }
    ChangePasswordScreen #error-label {
        color: $error;
        margin-bottom: 1;
        height: auto;
    }
    ChangePasswordScreen #buttons {
        layout: horizontal;
        height: auto;
        align: right middle;
    }
    ChangePasswordScreen Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="dialog"):
            yield Static("Change Password", id="title")
            yield Input(placeholder="Current password", password=True, id="old-password")
            yield Input(placeholder="New password (min 10 chars)", password=True, id="new-password")
            yield Input(placeholder="Confirm new password", password=True, id="confirm-password")
            yield Label("", id="error-label")
            with Static(id="buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#old-password", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._try_save()
        elif event.button.id == "cancel-btn":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "old-password":
            self.query_one("#new-password", Input).focus()
        elif event.input.id == "new-password":
            self.query_one("#confirm-password", Input).focus()
        else:
            self._try_save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _try_save(self) -> None:
        old = self.query_one("#old-password", Input).value
        new = self.query_one("#new-password", Input).value
        confirm = self.query_one("#confirm-password", Input).value

        if new != confirm:
            self._show_error("Passwords do not match.")
            return

        self._show_error("")
        self.app.send_ws({  # type: ignore[attr-defined]
            "type": C2S.CHANGE_PASSWORD,
            "old_password": old,
            "new_password": new,
        })

    def show_server_error(self, reason: str) -> None:
        msg = _ERROR_MESSAGES.get(reason, f"Password change failed: {reason}")
        self._show_error(msg)

    def _show_error(self, msg: str) -> None:
        label = self.query_one("#error-label", Label)
        label.update(msg)
