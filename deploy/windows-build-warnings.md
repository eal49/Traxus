# Windows .exe Build — Warnings & Gotchas

Captured during release workflow design exploration (2026-03-14).
Reference this before touching `traxus.spec` or `.github/workflows/release.yml`.

---

## Build Environment

### Python version is 3.13, not 3.14
GitHub Actions `windows-latest` does not yet ship Python 3.14.
The build uses **Python 3.13**. The Traxus codebase is compatible (no 3.14-specific
features identified — `match` statements, `|` unions, and `from __future__ import
annotations` are all 3.10+). If 3.14 syntax is ever introduced, the CI build will
break before users see it.

**Action:** When GHA ships 3.14, update `python-version` in `release.yml`.

---

## PyInstaller Spec

### `console=True` is mandatory — never change it
Textual is a terminal UI framework. If `console=False` is set in `traxus.spec`,
Windows opens a GUI window with no attached terminal. The TUI renders into nothing
and the app appears to hang silently. There is no error message.

```python
# traxus.spec — this line must always be True
exe = EXE(..., console=True, ...)
```

### `app.tcss` must be bundled alongside `app.py`
Textual resolves `CSS_PATH` via `inspect.getfile(TraxusApp)` and looks for the
`.tcss` file relative to that path. In a `--onefile` build, frozen files extract
to `sys._MEIPASS` at runtime. The spec must include:

```python
datas=[('client/app.tcss', 'client'), ...]
```

This places `app.tcss` at `_MEIPASS/client/app.tcss` — exactly where Textual
looks. If this line is missing, the app crashes at startup with a CSS file not
found error.

### sounddevice loads PortAudio via cffi — DLL path is non-obvious
sounddevice does **not** use a standard system PortAudio install. It bundles its
own DLL in `_sounddevice_data/portaudio-binaries/`:

```
libportaudio64bit.dll        (300 KB)  ← used at runtime
libportaudio64bit-asio.dll   (335 KB)  ← ASIO driver variant
```

These must be explicitly included in the spec `binaries` list. If missing,
`AUDIO_AVAILABLE` silently becomes `False` at runtime and voice is disabled
with no error — which looks like a bug, not a missing DLL.

### numpy bundles a 19 MB OpenBLAS DLL
`numpy.libs/libscipy_openblas64_-xxx.dll` is ~19 MB. Traxus only uses numpy for
ADPCM (basic integer arithmetic, no BLAS), but PyInstaller bundles the entire
numpy package. **Expect the final `.exe` to be 50–70 MB.**

This is normal. Do not try to strip numpy.libs without testing — removing it
causes a cryptic import error at startup.

### UPX compression is OFF by default — keep it that way
UPX can reduce binary size ~30% but:
- Increases cold-start time (decompression on launch)
- Triggers antivirus false positives on some Windows Defender configurations
- Provides no benefit for a ~60 MB binary where the DLLs dominate size

Set `upx=False` in the spec.

---

## User Experience

### Double-clicking from Explorer closes the window on exit
If a user launches `traxus.exe` by double-clicking it in Windows Explorer, Windows
opens a temporary cmd.exe console. When the app exits (normally or on crash), that
console closes immediately — the user sees nothing.

**Mitigation options (not yet implemented):**
- Add "Press Enter to exit" on clean shutdown / error
- Release notes should say: "Run from Windows Terminal or an existing terminal"

### Textual looks bad in legacy cmd.exe
Traxus uses Unicode box-drawing characters and 24-bit colour. In the legacy
Windows console host (`conhost.exe` / old cmd.exe), these render as garbage or
fall back to ASCII. Windows Terminal, PowerShell 7+, and VS Code terminal all
work correctly.

**Mitigation:** Document minimum terminal requirement in the GitHub Release
description.

---

## CI / Workflow

### `test_multiclient_ptt` is flaky — may be worse on Windows GHA runners
This test starts a real server subprocess and measures Textual pump latency.
It has been observed to fail locally when a port is already in use. GHA Windows
runners are slower and noisier than Linux runners, which may increase flakiness.

**Options if it becomes a problem:**
1. Add a retry mechanism in the test
2. Mark it as an expected flaky test and skip on CI
3. Fix the underlying port-reuse issue in the test fixture

### Tests run on Linux (ubuntu-latest) for the test job
The build job runs on `windows-latest`, the test job on `ubuntu-latest` (faster,
cheaper). Platform-specific bugs (Windows path separators, asyncio policy
differences) would not be caught by this setup.

If a Windows-specific bug appears, add a second test job on `windows-latest`
temporarily to diagnose.

---

## Versioning

### The build embeds Python 3.13 — users never need Python installed
The `.exe` is fully self-contained. Users on Windows 7+ (64-bit) can run it with
no prerequisites. Python version on the user's machine is irrelevant.

### `VERSION` in `shared/message_types.py` is the protocol version, not the release version
Bumping `VERSION` breaks all connected clients until they update. It should only
be changed when the WebSocket protocol changes, not on every release. Keep these
two versioning concerns separate.
