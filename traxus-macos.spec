# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Traxus macOS client (Apple Silicon arm64).
# Build with:  pyinstaller traxus-macos.spec
# Output:      dist/traxus  (Unix executable, ~60-80 MB, self-contained)
#
# First-run Gatekeeper note: macOS will block an unsigned binary with
# "cannot be opened because it is from an unidentified developer."
# Workaround:  xattr -rd com.apple.quarantine ./traxus
# Or right-click → Open in Finder and click Open in the dialog.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
import sounddevice
import certifi

# ── Locate native dylib ───────────────────────────────────────────────────────

_sd_binaries_dir = (
    Path(sounddevice.__file__).parent
    / "_sounddevice_data"
    / "portaudio-binaries"
)
# Glob for whatever dylib sounddevice ships (name varies across versions).
_portaudio_dylib = next(_sd_binaries_dir.glob("libportaudio*.dylib"), None)
if _portaudio_dylib is None:
    raise FileNotFoundError(
        f"No libportaudio*.dylib found in {_sd_binaries_dir}. "
        "Ensure sounddevice is installed: pip install sounddevice"
    )

# ── Build configuration ───────────────────────────────────────────────────────

block_cipher = None

a = Analysis(
    ["client/main.py"],
    pathex=[],
    binaries=[
        # PortAudio dylib — must land at _sounddevice_data/portaudio-binaries/
        # inside the archive so sounddevice's cffi loader finds it at runtime.
        (str(_portaudio_dylib), "_sounddevice_data/portaudio-binaries"),
    ],
    datas=[
        # Textual CSS — must sit alongside app.py inside the archive.
        ("client/app.tcss", "client"),
        # Textual data files: tree-sitter highlight grammars, etc.
        *collect_data_files("textual"),
        # aiortc and av metadata/type stubs.
        *collect_data_files("aiortc"),
        *collect_data_files("av"),
        # CA certificate bundle for wss:// TLS verification.
        (certifi.where(), "certifi"),
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # MUST be True — Textual is a terminal UI; console=False produces a silent hang.
    console=True,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
