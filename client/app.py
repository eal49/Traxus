"""
TraxusApp — the root Textual application.

Responsibilities:
  • Push LoginScreen on startup
  • Start WsWorker via run_worker() when user hits Connect
  • Route server messages to the active ChatScreen
  • Dispatch slash commands and plain messages to the server
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive

from client.audio_engine import AUDIO_AVAILABLE, AudioEngine
from client.commands import HELP_TEXT, ParsedCommand, parse_input
from client.screens.login_screen import LoginScreen
from client.ws_worker import WsWorker
from shared import voice_protocol
from shared.message_types import C2S, S2C

if TYPE_CHECKING:
    from client.screens.chat_screen import ChatScreen

PTT_HOLD_DEBOUNCE_MS = 300
PTT_HOLD_INITIAL_DEBOUNCE_MS = 800  # > Windows initial key-repeat delay (~500 ms)
VAD_HANGOVER_MS = 400

_VAD_SENSITIVITY_THRESHOLDS: dict[str, float] = {
    "low":       600.0,
    "medium":    400.0,
    "high":      250.0,
    "very_high": 100.0,
}


class TraxusApp(App):
    """Root application."""

    CSS_PATH = "app.tcss"
    TITLE = "Traxus"
    SUB_TITLE = "Terminal Chat"
    BINDINGS = []

    # ── App-level reactive state ──────────────────────────────────────────────

    connection_state: reactive[str]    = reactive("disconnected")
    current_channel: reactive[str]     = reactive("general")
    current_voice_channel: reactive[str] = reactive("")
    username: reactive[str]            = reactive("")

    # ── Custom messages posted by WsWorker ────────────────────────────────────

    class ServerMessage(Message):
        def __init__(self, payload: dict) -> None:
            super().__init__()
            self.payload = payload

    class ConnectionStateChanged(Message):
        def __init__(self, state: str, detail: str = "") -> None:
            super().__init__()
            self.state  = state
            self.detail = detail

    class AudioFrame(Message):
        def __init__(self, data: bytes) -> None:
            super().__init__()
            self.data = data

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._ws_worker: WsWorker | None = None
        self._audio_engine: AudioEngine = AudioEngine()
        self._capture_worker = None
        self._ptt_debounce_task: asyncio.Task | None = None
        self._vad_hangover_task: asyncio.Task | None = None
        self._channel_members: dict[str, list[dict]] = {}
        self._voice_users: list[dict] = []
        from client.settings import load_settings
        settings = load_settings()
        self._ptt_key: str = settings.get("ptt_key", "f9")
        self._ptt_mode: str = settings.get("ptt_mode", "toggle")
        self._vad_sensitivity: str = settings.get("vad_sensitivity", "high")
        self._vad_custom_threshold: float = float(settings.get("vad_custom_threshold", 50.0))
        self.push_screen(LoginScreen())

    # ── Called by LoginScreen ─────────────────────────────────────────────────

    def connect_to_server(self, server_url: str, username: str) -> None:
        self.username = username
        self._ws_worker = WsWorker(self)
        self.run_worker(
            self._ws_worker.run(server_url, username),
            exclusive=True,
            name="ws_connection",
        )

    # ── Called by ChatScreen widgets ──────────────────────────────────────────

    def join_channel(self, channel: str) -> None:
        self._send({
            "type": C2S.JOIN,
            "channel": channel,
        })

    def handle_input(self, text: str) -> None:
        cmd = parse_input(text)
        if cmd is None:
            # Plain message
            self._send({
                "type": C2S.MESSAGE,
                "channel": self.current_channel,
                "content": text,
            })
            return
        self._execute_command(cmd)

    def _execute_command(self, cmd: ParsedCommand) -> None:
        match cmd.name:
            case "join":
                if cmd.args:
                    ch = cmd.args[0].lstrip("#")
                    self.join_channel(ch)
                else:
                    self._local("/join <channel>")

            case "leave":
                ch = cmd.args[0].lstrip("#") if cmd.args else self.current_channel
                self._send({"type": C2S.LEAVE, "channel": ch})

            case "nick":
                if cmd.args:
                    self._send({"type": C2S.NICK, "new_nick": cmd.args[0]})
                else:
                    self._local("/nick <new_name>")

            case "channels":
                self._send({"type": C2S.LIST_CHANNELS})

            case "create":
                if cmd.args:
                    self._send({"type": C2S.CREATE, "channel": cmd.args[0].lstrip("#")})
                else:
                    self._local("/create <channel-name>")

            case "vcreate":
                if cmd.args:
                    self._send({
                        "type": C2S.CREATE,
                        "channel": cmd.args[0].lstrip("#"),
                        "channel_type": "voice",
                    })
                else:
                    self._local("/vcreate <channel-name>")

            case "vjoin":
                if not AUDIO_AVAILABLE:
                    self._local("Voice not available: sounddevice/numpy not installed.")
                    return
                if cmd.args:
                    ch = cmd.args[0].lstrip("#")
                    self._send({"type": C2S.VOICE_JOIN, "channel": ch})
                else:
                    self._local("/vjoin <channel>")

            case "vleave":
                if not AUDIO_AVAILABLE:
                    self._local("Voice not available: sounddevice/numpy not installed.")
                    return
                ch = cmd.args[0].lstrip("#") if cmd.args else self.current_voice_channel
                if ch:
                    self._send({"type": C2S.VOICE_LEAVE, "channel": ch})
                else:
                    self._local("Not in a voice channel.")

            case "who":
                members = self._channel_members.get(self.current_channel, [])
                if members:
                    names = ", ".join(m.get("username", "?") for m in members)
                    self._local(f"Members in #{self.current_channel}: {names}")
                else:
                    self._local(f"No member info for #{self.current_channel}.")

            case "help":
                chat = self._chat()
                if chat:
                    chat.append_local("  ── Traxus Commands ──")
                    for line in HELP_TEXT.splitlines():
                        chat.append_local(line)

            case "settings":
                from client.screens.settings_screen import SettingsScreen
                from client.settings import save_settings

                def _on_settings_result(new_key: str | None) -> None:
                    if new_key is not None:
                        self._ptt_key = new_key
                        save_settings({
                            "ptt_key": self._ptt_key,
                            "ptt_mode": self._ptt_mode,
                            "vad_sensitivity": self._vad_sensitivity,
                            "vad_custom_threshold": self._vad_custom_threshold,
                        })
                    # Re-sync VAD state: if we should be listening but aren't,
                    # restart; if we shouldn't be but are, stop.
                    self._sync_vad_state()

                self.push_screen(SettingsScreen(), _on_settings_result)

            case "quit":
                if self._ws_worker:
                    self._ws_worker.stop()
                self.exit()

            case _:
                self._local(
                    f"Unknown command: /{cmd.name}  —  type /help for a list"
                )

    # ── Message handlers (posted by WsWorker) ────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if event.key == self._ptt_key:
            event.stop()
            if self._ptt_mode == "hold" and not self._ptt_key.startswith("mouse"):
                if not self._audio_engine.transmitting:
                    self.start_ptt()
                    self._arm_ptt_debounce(PTT_HOLD_INITIAL_DEBOUNCE_MS)
                else:
                    self._arm_ptt_debounce()  # key-repeat: reset to short timeout
            else:
                self.toggle_ptt()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if self._ptt_key.startswith("mouse"):
            try:
                if event.button == int(self._ptt_key[5:]):
                    event.stop()
                    if self._ptt_mode == "hold":
                        self.start_ptt()
                    else:
                        self.toggle_ptt()
            except ValueError:
                pass

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._ptt_mode == "hold" and self._ptt_key.startswith("mouse"):
            try:
                if event.button == int(self._ptt_key[5:]):
                    event.stop()
                    self.stop_ptt()
            except ValueError:
                pass

    def action_ptt_toggle(self) -> None:
        self.toggle_ptt()

    def toggle_ptt(self) -> None:
        if self._audio_engine.transmitting:
            self.stop_ptt()
        else:
            self.start_ptt()

    def start_ptt(self) -> None:
        if not AUDIO_AVAILABLE:
            self._local("Voice not available: sounddevice/numpy not installed.")
            return
        if not self.current_voice_channel:
            self._local("Join a voice channel first with /vjoin <channel>.")
            return
        if self._audio_engine.transmitting:
            return
        self._audio_engine.transmitting = True
        chat = self._chat()
        if chat:
            chat.update_ptt(True)
        loop = asyncio.get_running_loop()
        self._audio_engine.start(loop)
        self._capture_worker = self.run_worker(
            self._audio_engine.capture_loop(
                self.current_voice_channel,
                self._send_voice_frame,
            ),
            name="ptt_capture",
        )

    def stop_ptt(self) -> None:
        if not self._audio_engine.transmitting:
            return
        self._cancel_ptt_debounce()
        self._audio_engine.transmitting = False
        # In VAD mode the stream stays open (managed by _exit_vad_listening).
        if self._ptt_mode != "vad":
            self._audio_engine.stop()
        if self._capture_worker is not None:
            self._capture_worker.cancel()
            self._capture_worker = None
        chat = self._chat()
        if chat:
            chat.update_ptt(False)

    def _arm_ptt_debounce(self, delay_ms: int = PTT_HOLD_DEBOUNCE_MS) -> None:
        self._cancel_ptt_debounce()
        loop = asyncio.get_running_loop()
        self._ptt_debounce_task = loop.create_task(self._ptt_debounce_coro(delay_ms))

    def _cancel_ptt_debounce(self) -> None:
        if self._ptt_debounce_task is not None and not self._ptt_debounce_task.done():
            self._ptt_debounce_task.cancel()
        self._ptt_debounce_task = None

    async def _ptt_debounce_coro(self, delay_ms: int = PTT_HOLD_DEBOUNCE_MS) -> None:
        try:
            await asyncio.sleep(delay_ms / 1000)
            self.stop_ptt()
        except asyncio.CancelledError:
            pass

    def _arm_vad_hangover(self) -> None:
        self._cancel_vad_hangover()
        loop = asyncio.get_running_loop()
        self._vad_hangover_task = loop.create_task(self._vad_hangover_coro())

    def _cancel_vad_hangover(self) -> None:
        if self._vad_hangover_task is not None and not self._vad_hangover_task.done():
            self._vad_hangover_task.cancel()
        self._vad_hangover_task = None

    async def _vad_hangover_coro(self) -> None:
        try:
            await asyncio.sleep(VAD_HANGOVER_MS / 1000)
            self.stop_ptt()
        except asyncio.CancelledError:
            pass

    def _on_vad_state(self, is_voice: bool) -> None:
        """Called from the asyncio loop when VAD detects a voice/silence transition."""
        if is_voice:
            self._cancel_vad_hangover()
            if not self._audio_engine.transmitting:
                self.start_ptt()
        else:
            self._arm_vad_hangover()

    def _get_vad_threshold(self) -> float:
        """Resolve the current VAD threshold to a float."""
        if self._vad_sensitivity == "custom":
            return self._vad_custom_threshold
        return _VAD_SENSITIVITY_THRESHOLDS.get(self._vad_sensitivity, 200.0)

    def _enter_vad_listening(self) -> None:
        """Open the mic stream for VAD and update the UI to show LISTENING."""
        if not AUDIO_AVAILABLE:
            return
        threshold = self._get_vad_threshold()
        loop = asyncio.get_running_loop()
        self._audio_engine.start_vad(loop, threshold, self._on_vad_state)
        chat = self._chat()
        if chat:
            chat.update_vad_listening(True)

    def _exit_vad_listening(self) -> None:
        """Close the VAD mic stream and clear the LISTENING indicator."""
        self._cancel_vad_hangover()
        self._audio_engine.stop_vad()
        chat = self._chat()
        if chat:
            chat.update_vad_listening(False)

    def _sync_vad_state(self) -> None:
        """Ensure VAD is active iff ptt_mode=='vad' and in a voice channel."""
        should_listen = (
            AUDIO_AVAILABLE
            and self._ptt_mode == "vad"
            and bool(self.current_voice_channel)
        )
        is_listening = self._audio_engine._vad_active
        if should_listen and not is_listening:
            self._enter_vad_listening()
        elif not should_listen and is_listening:
            self._exit_vad_listening()

    async def _send_voice_frame(self, channel: str, pcm_bytes: bytes) -> None:
        if self._ws_worker:
            from shared import voice_protocol as vp
            self._ws_worker.enqueue_binary(vp.pack_c2s(channel, pcm_bytes))

    # ── Message handlers (posted by WsWorker) ────────────────────────────────

    def on_traxus_app_audio_frame(self, msg: "TraxusApp.AudioFrame") -> None:
        try:
            _channel, _username, pcm_bytes = voice_protocol.unpack_s2c(msg.data)
            self._audio_engine.play(pcm_bytes)   # instant: queues to playback thread
        except Exception:
            pass

    def on_traxus_app_server_message(self, msg: "TraxusApp.ServerMessage") -> None:
        payload = msg.payload
        t = payload.get("type", "")
        chat = self._chat()

        match t:
            case "auth_ok":
                self.username = payload.get("username", self.username)
                # Switch to chat screen
                from client.screens.chat_screen import ChatScreen
                self.switch_screen(ChatScreen())

            case "auth_error":
                reason = payload.get("reason", "unknown")
                login = self.query_one(LoginScreen)
                reason_text = {
                    "username_taken":   "That username is already taken.",
                    "invalid_username": "Invalid username. Use 1–32 non-space chars.",
                }.get(reason, f"Auth failed: {reason}")
                login.show_error(reason_text)

            case "channel_list":
                if chat:
                    chat.update_channel_list(payload.get("channels", []))

            case "joined":
                channel = payload.get("channel", "")
                self.current_channel = channel
                if chat:
                    chat.set_active_channel(channel)
                    chat.load_history(payload.get("history", []))
                    chat.append_system(f"Joined #{channel}")
                    members = self._channel_members.get(channel, [])
                    chat.update_members(members)

            case "left":
                channel = payload.get("channel", "")
                if chat:
                    chat.append_system(f"Left #{channel}")

            case "chat":
                if chat:
                    chat.append_chat(payload)

            case "system":
                content = payload.get("content", "")
                if chat:
                    chat.append_system(content)
                self._update_members_from_system(content, chat)

            case "nick_changed":
                old = payload.get("old_nick", "")
                new = payload.get("new_nick", "")
                if payload.get("user_id") and chat:
                    chat.append_system(f"{old} is now known as {new}")
                # Update our own displayed nick if it's us
                if old == self.username:
                    self.username = new
                    if chat:
                        chat.update_status(self.connection_state, nick=new)
                # Update member lists
                changed = False
                for members in self._channel_members.values():
                    for m in members:
                        if m.get("username") == old:
                            m["username"] = new
                            changed = True
                if changed and chat:
                    members = self._channel_members.get(self.current_channel, [])
                    chat.update_members(members)

            case "channel_created":
                ch  = payload.get("channel", "")
                who = payload.get("created_by", "someone")
                if chat:
                    chat.append_system(f"{who} created #{ch}")

            case "voice_state":
                channel = payload.get("channel", "")
                users = payload.get("users", [])
                prev_channel = self.current_voice_channel
                self.current_voice_channel = channel if users else ""
                self._voice_users = users
                if chat:
                    chat.update_voice_state(users)
                    chat.update_member_voice(users)
                # VAD mic lifecycle: enter listening when joining, exit when leaving.
                if self._ptt_mode == "vad":
                    if self.current_voice_channel and not prev_channel:
                        self._enter_vad_listening()
                    elif not self.current_voice_channel and prev_channel:
                        self._exit_vad_listening()

            case "user_list":
                channel = payload.get("channel", "")
                users = payload.get("users", [])
                self._channel_members[channel] = users
                if channel == self.current_channel and chat:
                    chat.update_members(users)

            case "pong":
                ts = payload.get("ts", 0.0)
                latency_ms = int((time.time() - ts) * 1000)
                if chat:
                    chat.update_status("connected", latency=latency_ms)

            case "error":
                msg_text = payload.get("message", payload.get("code", "Unknown error"))
                if chat:
                    chat.append_error(msg_text)
                else:
                    # Still on login screen — surface auth errors
                    try:
                        self.query_one(LoginScreen).show_error(msg_text)
                    except Exception:
                        pass

    def on_traxus_app_connection_state_changed(
        self, msg: "TraxusApp.ConnectionStateChanged"
    ) -> None:
        self.connection_state = msg.state
        chat = self._chat()
        if chat:
            chat.update_status(msg.state, nick=self.username)
            if msg.state == "reconnecting":
                chat.append_system("Connection lost — reconnecting…")
            elif msg.state == "connected":
                chat.append_system("Reconnected.")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _send(self, payload: dict) -> None:
        if self._ws_worker:
            self._ws_worker.enqueue(payload)

    def _local(self, text: str) -> None:
        chat = self._chat()
        if chat:
            chat.append_system(text)

    def _chat(self) -> "ChatScreen | None":
        """Return the ChatScreen even when a modal is on top of it."""
        from client.screens.chat_screen import ChatScreen
        try:
            for screen in reversed(self.screen_stack):
                if isinstance(screen, ChatScreen):
                    return screen
        except Exception:
            pass
        return None

    def _update_members_from_system(self, content: str, chat: "ChatScreen | None") -> None:
        import re
        # "alice joined #general"
        m = re.match(r"^(\S+) joined #(\S+)$", content)
        if m:
            username, channel = m.group(1), m.group(2)
            members = self._channel_members.get(channel, [])
            if not any(u.get("username") == username for u in members):
                members.append({"user_id": "", "username": username})
                self._channel_members[channel] = members
            if channel == self.current_channel and chat:
                chat.update_members(members)
            return

        # "alice left #general"
        m = re.match(r"^(\S+) left #(\S+)$", content)
        if m:
            username, channel = m.group(1), m.group(2)
            members = self._channel_members.get(channel, [])
            members = [u for u in members if u.get("username") != username]
            self._channel_members[channel] = members
            if channel == self.current_channel and chat:
                chat.update_members(members)
            return

        # "alice disconnected"
        m = re.match(r"^(\S+) disconnected$", content)
        if m:
            username = m.group(1)
            refreshed = False
            for ch, members in self._channel_members.items():
                before = len(members)
                members[:] = [u for u in members if u.get("username") != username]
                if len(members) < before and ch == self.current_channel:
                    refreshed = True
            if refreshed and chat:
                chat.update_members(self._channel_members.get(self.current_channel, []))
