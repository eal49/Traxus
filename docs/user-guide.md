# Traxus — Client User Guide

Traxus is a terminal-based chat and voice application. Everything runs in your
terminal window — no browser, no Electron, no GPU required.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Connecting to a Server](#2-connecting-to-a-server)
3. [Interface Overview](#3-interface-overview)
4. [Text Chat](#4-text-chat)
5. [Voice Channels](#5-voice-channels)
6. [Settings](#6-settings)
7. [System Tray Icon](#7-system-tray-icon)
8. [Slash Command Reference](#8-slash-command-reference)
9. [Keyboard Shortcuts & Tips](#9-keyboard-shortcuts--tips)

---

## 1. Installation

### From source (Python)

```bash
pip install textual websockets certifi
```

For voice support (microphone, speakers, WebRTC):

```bash
pip install sounddevice numpy aiortc av
```

For the system tray icon:

```bash
pip install pystray Pillow
```

Then run:

```bash
python -m client.main
```

### Pre-built binaries

Download the latest release from the GitHub Releases page:

| Platform | File |
|---|---|
| Windows (64-bit) | `traxus-vX.Y.Z-windows.exe` |
| macOS (Apple Silicon) | `traxus-vX.Y.Z-macos-arm64` |

The binaries are self-contained — no Python installation required.

**Windows:** Run from Windows Terminal or PowerShell (not by double-clicking from
Explorer — the app requires a terminal to render).

**macOS:** On first run, Gatekeeper blocks unsigned binaries. Clear the quarantine
flag once:

```bash
xattr -rd com.apple.quarantine ./traxus-vX.Y.Z-macos-arm64
chmod +x ./traxus-vX.Y.Z-macos-arm64
./traxus-vX.Y.Z-macos-arm64
```

Alternatively: right-click the file in Finder → Open → click Open in the dialog.

---

## 2. Connecting to a Server

On launch you are shown the login screen:

```
┌──────────────────────────────────────────────────────┐
│                     TRAXUS                            │
│          Terminal chat — connect to a server          │
│                                                       │
│  Server URL  ──────────────────────────────────────  │
│  Username    ──────────────────────────────────────  │
│  Password    ──────────────────────────────────────  │
│                                                       │
│                  [ Connect ]                          │
└──────────────────────────────────────────────────────┘
```

| Field | What to enter |
|---|---|
| **Server URL** | WebSocket address of the server, e.g. `wss://yourserver.example.com` for a public server, or `ws://localhost:8765` for a local one. |
| **Username** | 1–32 characters, no spaces. Must be unique on the server. |
| **Password** | Only required if the server has password authentication enabled. Leave blank for servers that don't require it — they ignore this field entirely. |

The server URL and username are **saved automatically** and pre-filled on the next
launch. The password is never saved.

Press **Tab** to move between fields, **Enter** or click **Connect** to connect.

---

## 3. Interface Overview

```
┌──────────────┬──────────────────────────────────────┬──────────────┐
│ TEXT          │ [10:42] alice  hey, anyone around?   │ MEMBERS      │
│  # general ◄ │ [10:43] bob    yep                   │  alice       │
│  # random    │ [10:43] carol  joining voice now      │  bob         │
│  # dev       │                                       │  carol       │
│              │                                       │              │
│ VOICE        │                                       │ IN VOICE     │
│  ♪ dev-voice │                                       │  bob ██ 80%  │
│    · bob     │                                       │  carol ██100%│
│    · carol   │                                       │              │
├──────────────┴──────────────────────────────────────┴──────────────┤
│ #general ›                                                          │
├─────────────────────────────────────────────────────────────────────┤
│ ● connected  alice  42 ms  ♪ dev-voice                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Panels

| Panel | Description |
|---|---|
| **Left sidebar** | Lists text channels (prefixed `#`) and voice channels (prefixed `♪`). The active text channel is highlighted. Voice channel members are shown indented beneath the channel. |
| **Center — message view** | Scrolling chat history with timestamps and colour-coded nicknames. System messages (joins, leaves, nicks) appear in muted text. |
| **Right — member panel** | Current members of the active text channel. When in a voice channel, an **In Voice** section shows voice participants with their playback volume bar. |
| **Input bar** | Where you type messages and slash commands. Shows the current channel name as a prompt. |
| **Status bar** | Connection state, your username, ping latency, current voice channel, and PTT indicator. |

### Status bar indicators

| Indicator | Meaning |
|---|---|
| `● connected` | Connected to the server |
| `◌ reconnecting` | Connection lost, retrying automatically |
| `✕ disconnected` | Not connected |
| `♪ channel-name` | Currently in this voice channel |
| `🎤 PTT ON` | Microphone is live (you are transmitting) |
| `42 ms` | Round-trip latency to the server |

---

## 4. Text Chat

### Sending messages

Type in the input bar and press **Enter**. Any text not starting with `/` is sent
as a chat message to the current channel.

### Channels

You are automatically joined to **#general** after connecting. Use `/join` to
switch channels and `/create` to make new ones. The sidebar updates in real time
as channels are created and members join or leave.

### Quoting a message

Type `/quote ` (with a trailing space) to enter **selection mode**. Use **Up/Down
arrows** to highlight a message in the chat, then press **Enter** to quote it. The
quoted text appears in your input bar prefixed with `> `. Press **Escape** to
cancel selection.

### Pinning a message

Type `/pin ` (with a trailing space) and select a message the same way as quoting.
The pinned message is displayed at the top of the channel for all members.

### Nick colours

Each user is assigned a colour automatically based on their username. You can
override your own nick colour with:

```
/color blue
/color #ff6600
/color reset
```

Named colours: `blue`, `green`, `yellow`, `red`, `pink`, `cyan`, `magenta`, `orange`.

---

## 5. Voice Channels

### Joining and leaving

```
/vjoin <channel>    — join a voice channel
/vleave             — leave the current voice channel
```

Once in a voice channel, WebRTC peer connections are established automatically
with all other participants. You hear their audio immediately; they hear yours
only when your microphone is gated open (see PTT modes below).

### PTT modes

Three modes control when your microphone transmits. Change the mode in `/settings`.

#### Toggle mode (default)

Press the PTT key (default **F9**) once to start transmitting. Press it again to
stop. The status bar shows `🎤 PTT ON` while active.

#### Hold mode

Hold the PTT key while you want to transmit. Release it to stop. Good for
walkie-talkie style communication.

#### VAD mode (voice activity detection)

The microphone stays open continuously and listens for your voice. Transmission
starts automatically when your speaking volume exceeds the threshold, and stops
after a short silence (400 ms hangover). No key to hold.

**Calibrating VAD sensitivity:** Go to `/settings → VAD Sensitivity`. A live
ASCII bar chart shows your microphone energy in real time. Move the threshold
line with **Up/Down** (fine) or **PgUp/PgDn** (coarse) until it sits just above
your background noise and below your speaking level. Press **Enter** to save.

Preset options: **Low**, **Medium**, **High** (default), **Very High**, or
**Custom** (set via calibration screen).

### Per-participant volume

In the **member panel**, each voice participant shows a volume bar. Navigate to a
participant with **Up/Down arrows** in the member panel, then use **Left/Right
arrows** to adjust their playback volume from 0 % to 200 %. The adjustment is
local — it only affects what you hear, not what they transmit.

At 100 % (default) the audio is unchanged. At 200 % the volume is boosted by
+12 dB. The gain curve is perceptual (squared power-law) so 50 % feels like the
true inverse of 200 %.

### Audio device selection

Go to `/settings → Input Device` or `/settings → Output Device` to choose a
specific microphone or speaker. The list shows all devices detected by
sounddevice. Select "System Default" to use the OS default device.

Device changes take effect **immediately without rejoining** the voice channel.
At most a brief moment of silence occurs during the swap.

### Microphone test

Run `/audioTest` while in a voice channel with at least one other participant.
The client sends 10 sine-wave tones (C major scale, one per second) through the
full WebRTC pipeline. The other participant hears the scale if the audio pipeline
is healthy.

### NAT traversal

Traxus uses Google's public STUN server (`stun:stun.l.google.com:19302`) to
negotiate peer-to-peer connections. This works for most home and office networks.

If two participants are both behind **strict symmetric NAT** (some corporate or
mobile networks), the direct connection may fail and voice will be silent. The
fix is a TURN relay server — see `deploy/deploy.md` for setup instructions.

---

## 6. Settings

Open with `/settings`. Press **Escape** or navigate to the close button to
dismiss.

| Setting | What it does |
|---|---|
| **PTT Key** | The key or mouse button that gates the microphone. Press any key to rebind. Middle-click (`mouse2`) is recommended for mouse PTT. |
| **PTT Mode** | Toggle / Hold / VAD — see [Voice Channels](#5-voice-channels). |
| **VAD Sensitivity** | Opens the live calibration screen to adjust the voice detection threshold. |
| **Input Device** | Choose the microphone. |
| **Output Device** | Choose the speaker or headphones. |

Settings are saved to `~/.config/traxus/settings.json` and loaded on next launch.

---

## 7. System Tray Icon

When `pystray` and `Pillow` are installed, Traxus places an icon in your OS
system tray that reflects the current state at a glance — useful when the
terminal is minimised or behind other windows.

### Icon states

| Icon | State |
|---|---|
| ![Disconnected](../Art/SystrayIcons/Disconnected.png) **Disconnected** | Not connected to a server (or reconnecting) |
| ![Connected](../Art/SystrayIcons/Connected.png) **Connected** | Connected to a server, not in a voice channel |
| ![VoiceConnected](../Art/SystrayIcons/VoiceConnected.png) **Voice connected** | In a voice channel, microphone idle |
| ![Listening](../Art/SystrayIcons/Listening.png) **Listening** | In a voice channel, VAD mode active and monitoring |
| ![Speaking](../Art/SystrayIcons/Speaking.png) **Speaking** | Transmitting — you are the only participant |
| ![SpeakingAndListening](../Art/SystrayIcons/SpeakingAndListening.png) **Speaking & listening** | Transmitting while others are present in the channel |

The icon updates in real time as you connect, join voice channels, and toggle PTT.

Right-clicking the icon shows a **Quit** menu item that exits the application.

### Installing the tray icon

If you are running from source:

```bash
pip install pystray Pillow
```

The pre-built `.exe` and macOS binary have pystray and Pillow bundled — no extra
install required.

### Making the icon visible on Windows

Windows hides new tray icons in the **notification overflow** (the `^` arrow on
the right side of the taskbar, near the clock) until you explicitly pin them to
the visible area.

**To make the Traxus icon always visible:**

1. Click the `^` arrow in the taskbar to expand hidden icons.
2. Drag the Traxus icon out of the overflow and onto the visible taskbar area.

Or via Settings:

1. Right-click an empty area of the taskbar → **Taskbar settings**.
2. Click **Other system tray icons**.
3. Toggle **Traxus** to **On**.

After this, the icon stays visible in the taskbar whenever the client is running.

---

## 8. Slash Command Reference

| Command | Description |
|---|---|
| `/join <channel>` | Switch to a text channel. Leading `#` is optional. |
| `/leave [channel]` | Leave a channel (defaults to the current one). |
| `/create <name>` | Create a new text channel. |
| `/vcreate <name>` | Create a new voice channel. |
| `/vjoin <channel>` | Join a voice channel (starts WebRTC audio). |
| `/vleave` | Leave the current voice channel. |
| `/nick <name>` | Change your display name (1–32 chars, no spaces). |
| `/channels` | List all channels on the server. |
| `/who` | List members of the current text channel. |
| `/settings` | Open the settings panel. |
| `/color <name\|#hex>` | Set your nick colour. Use `reset` to clear. |
| `/quote ` | Enter message selection mode to quote a line. |
| `/pin ` | Enter message selection mode to pin a line. |
| `/audioTest` | Send 10 test tones over the active voice channel. |
| `/help` | Print the command reference inline. |
| `/quit` | Disconnect and exit. |

> **Tip:** Type the first few letters of a command and press **Tab** to
> auto-complete. **Shift+Tab** cycles backwards through matches.

---

## 9. Keyboard Shortcuts & Tips

### Global shortcuts

| Key | Action |
|---|---|
| **F9** *(default)* | Toggle/hold PTT — fires even while typing |
| **Tab** | Complete a slash command name in the input bar |
| **Shift+Tab** | Cycle backwards through command completions |
| **Up arrow** | In the input bar: recall previous slash command |
| **Down arrow** | In the input bar: recall next slash command (or restore draft) |
| **Escape** | Cancel command completion / exit selection mode / close modal screens |

### Member panel shortcuts

| Key | Action |
|---|---|
| **Up / Down** | Navigate between voice participants |
| **Left arrow** | Decrease the selected participant's volume |
| **Right arrow** | Increase the selected participant's volume |

### Command history

Every slash command you submit is saved to
`~/.config/traxus/command_history.json` (up to 200 entries). Use **Up/Down** in
the input bar to cycle through past commands. Consecutive duplicates are
suppressed. Plain chat messages are excluded from history.

Your current draft is saved and restored when you navigate through history —
pressing **Down** past the most recent entry restores whatever you had typed.

### Login persistence

The last server URL and username you used are saved automatically. They are
pre-filled on the next launch so you can connect with a single **Enter**.
