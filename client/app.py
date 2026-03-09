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


class TraxusApp(App):
    """Root application."""

    CSS_PATH = "app.tcss"
    TITLE = "Traxus"
    SUB_TITLE = "Terminal Chat"
    BINDINGS = [Binding("f9", "ptt_toggle", "Toggle PTT", priority=True)]

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

            case "help":
                chat = self._chat()
                if chat:
                    chat.append_local("  ── Traxus Commands ──")
                    for line in HELP_TEXT.splitlines():
                        chat.append_local(line)

            case "quit":
                if self._ws_worker:
                    self._ws_worker.stop()
                self.exit()

            case _:
                self._local(
                    f"Unknown command: /{cmd.name}  —  type /help for a list"
                )

    # ── Message handlers (posted by WsWorker) ────────────────────────────────

    def action_ptt_toggle(self) -> None:
        self.toggle_ptt()

    def toggle_ptt(self) -> None:
        if not AUDIO_AVAILABLE:
            self._local("Voice not available: sounddevice/numpy not installed.")
            return
        if not self.current_voice_channel:
            self._local("Join a voice channel first with /vjoin <channel>.")
            return
        self._audio_engine.transmitting = not self._audio_engine.transmitting
        active = self._audio_engine.transmitting

        chat = self._chat()
        if chat:
            chat.update_ptt(active)

        if active:
            loop = asyncio.get_running_loop()
            self._audio_engine.start(loop)
            self._capture_worker = self.run_worker(
                self._audio_engine.capture_loop(
                    self.current_voice_channel,
                    self._send_voice_frame,
                ),
                name="ptt_capture",
            )
        else:
            self._audio_engine.stop()
            if self._capture_worker is not None:
                self._capture_worker.cancel()
                self._capture_worker = None

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

            case "left":
                channel = payload.get("channel", "")
                if chat:
                    chat.append_system(f"Left #{channel}")

            case "chat":
                if chat:
                    chat.append_chat(payload)

            case "system":
                if chat:
                    chat.append_system(payload.get("content", ""))

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

            case "channel_created":
                ch  = payload.get("channel", "")
                who = payload.get("created_by", "someone")
                if chat:
                    chat.append_system(f"{who} created #{ch}")

            case "voice_state":
                channel = payload.get("channel", "")
                users = payload.get("users", [])
                self.current_voice_channel = channel if users else ""
                if chat:
                    chat.update_voice_state(users)

            case "user_list":
                # Could populate a future members panel; for now just log it
                pass

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
        from client.screens.chat_screen import ChatScreen
        try:
            screen = self.screen
        except Exception:
            return None
        return screen if isinstance(screen, ChatScreen) else None
