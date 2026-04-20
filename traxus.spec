# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Traxus Windows client.
# Build with:  pyinstaller traxus.spec
# Output:      dist/traxus.exe  (~50-70 MB, self-contained, no Python required)
#
# See deploy/windows-build-warnings.md for known gotchas before editing.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sounddevice

# ── Locate native DLLs ────────────────────────────────────────────────────────

# sounddevice ships its own PortAudio DLL; it is not a system library.
_sd_binaries_dir = (
    Path(sounddevice.__file__).parent
    / "_sounddevice_data"
    / "portaudio-binaries"
)
_portaudio_dll = _sd_binaries_dir / "libportaudio64bit.dll"

# ── Build configuration ───────────────────────────────────────────────────────

block_cipher = None

a = Analysis(
    ["client/main.py"],
    pathex=[],
    binaries=[
        # PortAudio DLL — must land at _sounddevice_data/portaudio-binaries/
        # inside the archive so sounddevice's cffi loader finds it at runtime.
        (str(_portaudio_dll), "_sounddevice_data/portaudio-binaries"),
    ],
    datas=[
        # Textual CSS — resolved via inspect.getfile(TraxusApp); must sit
        # alongside app.py inside the archive (i.e. in the client/ subdir).
        ("client/app.tcss", "client"),
        # Textual data files: tree-sitter highlight grammars, etc.
        *collect_data_files("textual"),
        # aiortc and av metadata/type stubs.
        *collect_data_files("aiortc"),
        *collect_data_files("av"),
    ],
    hiddenimports=[
        # websockets uses lazy submodule imports that PyInstaller misses.
        "websockets.asyncio.client",
        "websockets.asyncio.server",
        "websockets.exceptions",
        # cffi backend required by sounddevice.
        "_cffi_backend",
        # aiortc codec modules — loaded dynamically via string lookup at runtime.
        "aiortc.codecs.opus",
        "aiortc.codecs.h264",
        "aiortc.codecs.vpx",
        "aiortc.codecs.g711",
        "aiortc.codecs.g722",
        "aiortc.codecs.base",
        # aioice ICE transport — lazy submodule used by aiortc.
        "aioice.stun",
        # av subpackages — Cython extensions loaded by name at runtime.
        "av.audio.frame",
        "av.video.frame",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="traxus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX disabled: causes antivirus false positives, no meaningful size benefit.
    # See deploy/windows-build-warnings.md — D4.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # MUST be True — Textual is a terminal UI; console=False produces a silent hang.
    # See deploy/windows-build-warnings.md — "console=True is mandatory".
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
