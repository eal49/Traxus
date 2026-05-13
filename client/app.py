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

from client.audio_engine import AUDIO_AVAILABLE, WEBRTC_AVAILABLE, AudioEngine
from client.commands import HELP_TEXT, ParsedCommand, parse_input
from client.screens.login_screen import LoginScreen
from client.widgets.input_bar import InputBar
from client.widgets.message_view import MessageView, _strip_markup
from client.ws_worker import WsWorker
from shared.message_types import C2S, S2C

if TYPE_CHECKING:
    from client.screens.chat_screen import ChatScreen

PTT_HOLD_DEBOUNCE_MS = 300
PTT_HOLD_INITIAL_DEBOUNCE_MS = 800  # > Windows initial key-repeat delay (~500 ms)
VAD_HANGOVER_MS = 400

# ── Audio test tone generation ────────────────────────────────────────────────

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

# C major scale C4→E5 (10 notes, one per count)
_AUDIO_TEST_FREQS = [261.63, 293.66, 329.63, 349.23, 392.00,
                     440.00, 493.88, 523.25, 587.33, 659.25]


def _gen_tone(freq: float, duration: float, sample_rate: int = 16000) -> "np.ndarray":
    t = _np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
    return (_np.sin(2.0 * _np.pi * freq * t) * 26214.0).astype(_np.int16)


def _apply_taper(tone: "np.ndarray", ramp_samples: int = 160) -> "np.ndarray":
    tone = tone.copy()
    ramp = (1.0 - _np.cos(_np.linspace(0.0, _np.pi, ramp_samples))) / 2.0
    tone[:ramp_samples] = (tone[:ramp_samples].astype(_np.float32) * ramp).astype(_np.int16)
    tone[-ramp_samples:] = (tone[-ramp_samples:].astype(_np.float32) * ramp[::-1]).astype(_np.int16)
    return tone

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

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._ws_worker: WsWorker | None = None
        self._ptt_debounce_task: asyncio.Task | None = None
        self._vad_hangover_task: asyncio.Task | None = None
        self._audio_test_running: bool = False
        self._channel_members: dict[str, list[dict]] = {}
        self._voice_users: list[dict] = []
        self._selection_command: str | None = None
        self._peer_manager = None  # PeerManager | None, created on vjoin
        self._transmitting: bool = False
        from client.settings import load_settings
        settings = load_settings()
        self._audio_engine: AudioEngine = AudioEngine()
        self._stun_server: str = settings.get("stun_server", "stun:stun.l.google.com:19302")
        self._ptt_key: str = settings.get("ptt_key", "f9")
        self._ptt_mode: str = settings.get("ptt_mode", "toggle")
        self._vad_sensitivity: str = settings.get("vad_sensitivity", "high")
        self._vad_custom_threshold: float = float(settings.get("vad_custom_threshold", 50.0))
        self._nick_color: str = settings.get("nick_color", "")
        self._input_device: "str | None" = settings.get("input_device") or None
        self._output_device: "str | None" = settings.get("output_device") or None
        self.push_screen(LoginScreen())

    async def on_unmount(self) -> None:
        if self._peer_manager is not None:
            await self._peer_manager.close_all()
            self._peer_manager = None

    # ── Called by LoginScreen ─────────────────────────────────────────────────

    def connect_to_server(self, server_url: str, username: str, password: str = "") -> None:
        self.username = username
        self._ws_worker = WsWorker(self)
        self.run_worker(
            self._ws_worker.run(server_url, username, password),
            exclusive=True,
            name="ws_connection",
        )

    # ── Called by ChatScreen widgets ──────────────────────────────────────────

    def join_channel(self, channel: str) -> None:
        if channel == self.current_channel:
            # Re-clicking the active channel: just refresh members, no join noise.
            self._send({"type": C2S.LIST_MEMBERS, "channel": channel})
            return
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
                if not WEBRTC_AVAILABLE:
                    self._local("Voice not available: sounddevice/numpy/aiortc not installed.")
                    return
                if cmd.args:
                    ch = cmd.args[0].lstrip("#")
                    self._send({"type": C2S.VOICE_JOIN, "channel": ch})
                else:
                    self._local("/vjoin <channel>")

            case "vleave":
                if not WEBRTC_AVAILABLE:
                    self._local("Voice not available: sounddevice/numpy/aiortc not installed.")
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
                        from client.settings import load_settings as _ls
                        settings = _ls()
                        settings.update({
                            "ptt_key": self._ptt_key,
                            "ptt_mode": self._ptt_mode,
                            "vad_sensitivity": self._vad_sensitivity,
                            "vad_custom_threshold": self._vad_custom_threshold,
                        })
                        save_settings(settings)
                    # Re-sync VAD state: if we should be listening but aren't,
                    # restart; if we shouldn't be but are, stop.
                    self._sync_vad_state()

                self.push_screen(SettingsScreen(), _on_settings_result)

            case "color":
                import re
                _COLOR_NAMES = {
                    "blue": "#5865f2", "green": "#57f287", "yellow": "#fee75c",
                    "pink": "#eb459e", "red": "#ed4245", "cyan": "#00b0f4",
                    "magenta": "#f47fff", "orange": "#faa61a", "white": "#ffffff",
                }
                if not cmd.args:
                    self._local("/color <name|#rrggbb|reset>")
                else:
                    arg = cmd.args[0].lower()
                    if arg == "reset":
                        self._set_nick_color("")
                        self._local("Nick color reset to default.")
                    elif arg in _COLOR_NAMES:
                        self._set_nick_color(_COLOR_NAMES[arg])
                        self._local(f"Nick color set to {arg} ({_COLOR_NAMES[arg]}).")
                    elif re.fullmatch(r"#[0-9a-fA-F]{6}", cmd.args[0]):
                        self._set_nick_color(cmd.args[0])
                        self._local(f"Nick color set to {cmd.args[0]}.")
                    else:
                        self._local(
                            f"Invalid color '{cmd.args[0]}'. Use a name (blue/green/…) or #rrggbb."
                        )

            case "quote":
                self._local("Type /quote followed by a space to enter line-selection mode.")

            case "pin":
                self._local("Type /pin followed by a space to enter line-selection mode.")

            case "audiotest":
                if not WEBRTC_AVAILABLE:
                    self._local("Voice not available: sounddevice/numpy/aiortc not installed.")
                elif not self._ws_worker:
                    self._local("Not connected.")
                elif not self.current_voice_channel:
                    self._local("Join a voice channel first (/vjoin <channel>).")
                elif self._audio_test_running:
                    self._local("Audio test already in progress.")
                else:
                    asyncio.get_running_loop().create_task(self._audio_test_task())

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
        if self._selection_command is not None:
            self._handle_selection_key(event)
            return
        if event.key == self._ptt_key:
            event.stop()
            if self._ptt_mode == "hold" and not self._ptt_key.startswith("mouse"):
                if not self._transmitting:
                    self.start_ptt()
                    self._arm_ptt_debounce(PTT_HOLD_INITIAL_DEBOUNCE_MS)
                else:
                    self._arm_ptt_debounce()  # key-repeat: reset to short timeout
            elif self._ptt_mode != "vad":
                self.toggle_ptt()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if self._ptt_key.startswith("mouse"):
            try:
                if event.button == int(self._ptt_key[5:]):
                    event.stop()
                    if self._ptt_mode == "hold":
                        self.start_ptt()
                    elif self._ptt_mode != "vad":
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
        if self._ptt_mode == "vad":
            return
        self.toggle_ptt()

    def toggle_ptt(self) -> None:
        if self._transmitting:
            self.stop_ptt()
        else:
            self.start_ptt()

    def start_ptt(self) -> None:
        if not WEBRTC_AVAILABLE:
            self._local("Voice not available: sounddevice/numpy/aiortc not installed.")
            return
        if not self.current_voice_channel:
            self._local("Join a voice channel first with /vjoin <channel>.")
            return
        if self._transmitting:
            return
        self._transmitting = True
        if self._peer_manager is not None:
            self._peer_manager.mic_track.set_transmitting(True)
        chat = self._chat()
        if chat:
            chat.update_ptt(True)

    def stop_ptt(self) -> None:
        if not self._transmitting:
            return
        self._cancel_ptt_debounce()
        self._transmitting = False
        if self._peer_manager is not None:
            self._peer_manager.mic_track.set_transmitting(False)
        chat = self._chat()
        if chat:
            chat.update_ptt(False)

    async def _handle_voice_state_webrtc(
        self, channel: str, users: list, prev_channel: str
    ) -> None:
        """Create/destroy PeerManager and connect to new peers on voice_state."""
        import sounddevice as sd
        from client.mic_track import MicTrack
        from client.peer_manager import PeerManager
        from client.settings import load_settings

        local_user = self.username
        new_usernames = {u["username"] for u in users if u["username"] != local_user}
        joined_voice = bool(channel) and not bool(prev_channel)
        left_voice = not bool(channel) and bool(prev_channel)

        if joined_voice and self._peer_manager is None:
            loop = asyncio.get_running_loop()
            _out_kwargs: dict = dict(samplerate=48000, channels=1, dtype="int16", latency=0.08)
            if self._output_device:
                _out_kwargs["device"] = self._output_device
            try:
                out_stream = sd.OutputStream(**_out_kwargs)
            except Exception:
                _out_kwargs.pop("device", None)
                out_stream = sd.OutputStream(**_out_kwargs)
            out_stream.start()
            from client.audio_mixer import AudioMixer
            mixer = AudioMixer(out_stream)
            mic = MicTrack(loop, device=self._input_device)
            self._peer_manager = PeerManager(
                mic_track=mic,
                mixer=mixer,
                ws_worker=self._ws_worker,  # type: ignore[arg-type]
                stun_url=self._stun_server,
            )
            # Only the lexicographically smaller username sends the offer to
            # avoid WebRTC glare (both sides sending offers simultaneously).
            for uname in new_usernames:
                if local_user < uname:
                    await self._peer_manager.connect(uname)
        elif left_voice and self._peer_manager is not None:
            await self._peer_manager.close_all()
            self._peer_manager = None
            self._transmitting = False
        elif self._peer_manager is not None:
            # Channel unchanged: connect to newly arrived peers
            existing = set(self._peer_manager._peers.keys())
            for uname in new_usernames - existing:
                if local_user < uname:
                    await self._peer_manager.connect(uname)
            for uname in existing - new_usernames:
                await self._peer_manager.disconnect(uname)

    async def _audio_test_task(self) -> None:
        self._audio_test_running = True
        try:
            if self._peer_manager is None:
                self._local("Join a voice channel first.")
                return
            self._local("Audio test: sending 10 tones...")
            loop = asyncio.get_running_loop()
            start = loop.time()
            frame_count = 0
            for freq in _AUDIO_TEST_FREQS:
                tone = _apply_taper(_gen_tone(freq, 1.0))
                for offset in range(0, len(tone), 320):
                    frame_samples = tone[offset:offset + 320]
                    # Inject directly into MicTrack queue so it flows via WebRTC
                    try:
                        self._peer_manager.mic_track._queue.put_nowait(
                            frame_samples.tobytes()
                        )
                    except Exception:
                        pass
                    frame_count += 1
                    target = start + frame_count * 0.020
                    delay = target - loop.time()
                    if delay > 0:
                        await asyncio.sleep(delay)
            self._local("Audio test complete.")
        finally:
            self._audio_test_running = False

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
            if not self._transmitting:
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

    # ── Message handlers (posted by WsWorker) ────────────────────────────────

    def on_traxus_app_server_message(self, msg: "TraxusApp.ServerMessage") -> None:
        payload = msg.payload
        t = payload.get("type", "")
        chat = self._chat()

        match t:
            case "auth_ok":
                self.username = payload.get("username", self.username)
                if self._ws_worker:
                    self._ws_worker.notify_auth_ok()
                # Switch to chat screen
                from client.screens.chat_screen import ChatScreen
                self.switch_screen(ChatScreen())

            case "auth_error":
                reason = payload.get("reason", "unknown")
                reason_text = {
                    "username_taken":   "That username is already taken.",
                    "invalid_username": "Invalid username. Use 1–32 non-space chars.",
                    "version_mismatch": f"Client version mismatch. Server requires v{payload.get('server_version', '?')}. Please update your client.",
                    "wrong_password":   "Incorrect password.",
                }.get(reason, f"Auth failed: {reason}")
                try:
                    screen = self.screen
                    if isinstance(screen, LoginScreen):
                        screen.show_error(reason_text)
                except Exception:
                    pass

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
                    chat.update_members([])
                    chat.update_pin(payload.get("pin"))

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
                # WebRTC peer lifecycle
                if WEBRTC_AVAILABLE:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._handle_voice_state_webrtc(
                        self.current_voice_channel, users, prev_channel
                    ))

            case S2C.VOICE_OFFER:
                if self._peer_manager is not None:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._peer_manager.on_offer(
                        payload.get("from_user", ""),
                        payload.get("sdp", ""),
                    ))

            case S2C.VOICE_ANSWER:
                if self._peer_manager is not None:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._peer_manager.on_answer(
                        payload.get("from_user", ""),
                        payload.get("sdp", ""),
                    ))

            case S2C.VOICE_ICE:
                if self._peer_manager is not None:
                    loop = asyncio.get_event_loop()
                    loop.create_task(self._peer_manager.on_ice(
                        payload.get("from_user", ""),
                        payload.get("candidate"),
                        payload.get("sdpMid", "0"),
                        payload.get("sdpMLineIndex", 0),
                    ))

            case "pin_added":
                if chat:
                    chat.update_pin(payload)

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
        if msg.state == "failed":
            # Initial connection failed — surface the error on the login screen.
            try:
                screen = self.screen
                if isinstance(screen, LoginScreen):
                    screen.show_error(msg.detail)
                    screen.reset_form()
            except Exception:
                pass
            return
        if chat:
            chat.update_status(msg.state, nick=self.username)
            if msg.state == "reconnecting":
                chat.append_system("Connection lost — reconnecting…")
            elif msg.state == "connected":
                chat.append_system("Reconnected.")

    def watch_current_voice_channel(self, name: str) -> None:
        chat = self._chat()
        if chat:
            chat.update_voice_channel(name)
        if not name:
            # Stopped being in a voice channel — halt any active audio.
            if self._transmitting:
                self.stop_ptt()
            if self._ptt_mode == "vad":
                self._exit_vad_listening()

    # ── Selection mode ────────────────────────────────────────────────────────

    def on_input_bar_selection_mode_requested(
        self, msg: InputBar.SelectionModeRequested
    ) -> None:
        self._selection_command = msg.command
        chat = self._chat()
        if chat:
            mv = chat._mv()
            if mv:
                mv.enter_selection_mode()
            try:
                chat.query_one(InputBar).disable()
            except Exception:
                pass

    def _handle_selection_key(self, event: events.Key) -> None:
        event.stop()
        key = event.key
        chat = self._chat()
        mv = chat._mv() if chat else None

        if key == "up" and mv:
            mv.move_cursor(-1)
        elif key == "down" and mv:
            mv.move_cursor(1)
        elif key == "enter":
            payload = mv.selected_payload() if mv else None
            markup = mv.selected_line_markup() if mv else ""
            cmd = self._selection_command
            self._exit_selection_mode()
            if cmd == "quote":
                self._handle_quote(payload, markup)
            elif cmd == "pin":
                self._handle_pin(payload)
        elif key == "escape":
            self._exit_selection_mode()

    def _exit_selection_mode(self) -> None:
        self._selection_command = None
        chat = self._chat()
        if chat:
            mv = chat._mv()
            if mv:
                mv.exit_selection_mode()
            try:
                chat.query_one(InputBar).enable()
            except Exception:
                pass

    def _handle_quote(self, payload: dict | None, markup: str) -> None:
        if payload is not None:
            nick = payload.get("username", "?")
            content = payload.get("content", "")
            # Strip any nested quote separator so quotes don't nest indefinitely
            raw = content.split(" › ")[0].strip() if " › " in content else content
            quoted = f"> @{nick}: {raw} › "
        else:
            plain = _strip_markup(markup).strip()
            quoted = f"> {plain} › "
        try:
            chat = self._chat()
            if chat:
                inp = chat.query_one(InputBar)
                inp.query_one("#message-input").value = quoted
                inp.focus_input()
        except Exception:
            pass

    def _handle_pin(self, payload: dict | None) -> None:
        if payload is None or not payload.get("msg_id"):
            self._local("Cannot pin this line — no message ID (system message or legacy).")
            return
        self._send({
            "type": C2S.PIN_MESSAGE,
            "channel": self.current_channel,
            "msg_id": payload["msg_id"],
            "username": payload.get("username", ""),
            "content": payload.get("content", ""),
        })

    # ── Audio device helpers ──────────────────────────────────────────────────

    def _restart_input_device(self, device: "str | None") -> None:
        from client.settings import load_settings, save_settings
        self._input_device = device
        settings = load_settings()
        settings["input_device"] = device
        save_settings(settings)
        if self._peer_manager is not None or (
            self._ptt_mode == "vad" and self.current_voice_channel
        ):
            self.run_worker(self._do_restart_input(device))

    async def _do_restart_input(self, device: "str | None") -> None:
        loop = asyncio.get_running_loop()
        if self._peer_manager is not None:
            try:
                await loop.run_in_executor(
                    None, self._peer_manager.mic_track.restart_stream, device
                )
            except Exception:
                pass
        if self._ptt_mode == "vad" and self.current_voice_channel:
            self._cancel_vad_hangover()
            chat = self._chat()
            if chat:
                chat.update_vad_listening(False)
            try:
                await loop.run_in_executor(None, self._audio_engine.stop_vad)
            except Exception:
                pass
            threshold = self._get_vad_threshold()
            try:
                await loop.run_in_executor(
                    None, self._audio_engine.start_vad, loop, threshold, self._on_vad_state
                )
            except Exception:
                pass
            if chat:
                chat.update_vad_listening(True)

    async def _do_restart_vad(self) -> None:
        if not (self._ptt_mode == "vad" and self.current_voice_channel):
            return
        loop = asyncio.get_running_loop()
        self._cancel_vad_hangover()
        chat = self._chat()
        if chat:
            chat.update_vad_listening(False)
        try:
            await loop.run_in_executor(None, self._audio_engine.stop_vad)
        except Exception:
            pass
        await asyncio.sleep(0.1)
        threshold = self._get_vad_threshold()
        try:
            await loop.run_in_executor(
                None, self._audio_engine.start_vad, loop, threshold, self._on_vad_state
            )
        except Exception as exc:
            self._local(f"VAD restart failed: {exc}")
            return
        if chat:
            chat.update_vad_listening(True)

    def _restart_output_device(self, device: "str | None") -> None:
        from client.settings import load_settings, save_settings
        self._output_device = device
        settings = load_settings()
        settings["output_device"] = device
        save_settings(settings)
        if self._peer_manager is not None:
            self.run_worker(self._do_restart_output(device))

    async def _do_restart_output(self, device: "str | None") -> None:
        loop = asyncio.get_running_loop()
        if self._peer_manager is not None:
            try:
                await loop.run_in_executor(
                    None, self._peer_manager.restart_output_stream, device
                )
            except Exception:
                pass

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _set_nick_color(self, hex_or_empty: str) -> None:
        from client.settings import load_settings, save_settings
        self._nick_color = hex_or_empty
        settings = load_settings()
        settings["nick_color"] = hex_or_empty
        save_settings(settings)

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
