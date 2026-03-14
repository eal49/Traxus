## Context

Traxus has no distribution mechanism. Users must clone the repo and run
`python -m client.main` with a full Python 3.14 environment. The goal is a
one-click Windows binary distributed via GitHub Releases.

The client depends on three categories of native material that must be handled
carefully for PyInstaller packaging:

1. **Textual CSS** — `client/app.tcss` loaded at runtime via `inspect.getfile()`
   relative to `app.py`
2. **PortAudio DLL** — `_sounddevice_data/portaudio-binaries/libportaudio64bit.dll`
   loaded by sounddevice via cffi (not a standard system library)
3. **numpy OpenBLAS DLL** — `numpy.libs/libscipy_openblas64_-xxx.dll` (~19 MB),
   bundled automatically by PyInstaller's numpy hook

Authoritative build notes live in `deploy/windows-build-warnings.md`.

## Goals / Non-Goals

**Goals:**
- Self-contained `traxus.exe` with full audio (PTT + VAD) — no Python install required
- Triggered automatically on `v*.*.*` tag push
- Tests must pass before a release binary is produced
- Release notes auto-generated from commit messages between tags
- Build spec version-controlled as `traxus.spec`

**Non-Goals:**
- macOS or Linux binaries (terminal apps on those platforms are trivially runnable
  from source with `pip install`)
- Code-signing the executable (requires a paid certificate; adds significant cost
  and process for a personal project)
- Server packaging or deployment automation (server CI is out of scope)
- `pyproject.toml` / PyPI distribution (exe is the distribution mechanism)

## Decisions

### D1 — PyInstaller `.spec` file, not inline CLI args

**Chosen:** A version-controlled `traxus.spec` at the repo root.

**Why:** The build requires explicit DLL paths, data file mappings, and hidden
import lists that would make inline `pyinstaller` CLI args unmaintainable. A spec
file is a plain Python script, easy to read, diff, and extend.

**Alternative:** Inline `--add-data`, `--hidden-import` flags in the workflow YAML.
Rejected: fragile, hard to test locally, diffs poorly.

### D2 — Python 3.13 for the build job

**Chosen:** `python-version: '3.13'` on `windows-latest`.

**Why:** GitHub Actions does not yet ship Python 3.14 (pre-release). The Traxus
codebase uses no 3.14-specific features — `match` statements, `|` unions, and
`from __future__ import annotations` are all 3.10+. The embedded Python in the
`.exe` will be 3.13; users never interact with it.

**When to revisit:** Once GHA ships 3.14, update `python-version` in `release.yml`.

### D3 — `--onefile` build (single executable)

**Chosen:** PyInstaller `--onefile` mode. One `.exe`, no installer, no folder.

**Why:** Maximum simplicity for users — download, double-click (from a terminal),
done. The startup extraction penalty (~1–2s on first run) is acceptable for a
terminal chat client.

**Alternative:** `--onedir` producing a zip of a folder. Faster startup but requires
users to keep the folder intact and find the right `.exe` inside it.

### D4 — UPX disabled

**Chosen:** `upx=False` in the spec.

**Why:** UPX compression triggers Windows Defender false positives on some
configurations, and the ~30% size reduction (~18 MB) is not meaningful for a
~60 MB binary where the OpenBLAS DLL dominates. Startup time is unaffected by
disabling UPX.

### D5 — Test job on `ubuntu-latest`, build on `windows-latest`

**Chosen:** Separate jobs on different runners. Tests run on Linux (fast, cheap);
the PyInstaller build runs on Windows (required for the `.exe`).

**Why:** Linux runners are ~2× faster and cheaper for pure Python tests. The
test suite has no platform-specific code that would behave differently on Linux.

**Risk:** Windows-specific bugs (path separators, asyncio policy, DLL loading)
would not be caught. Accepted — if a Windows-specific regression appears, add a
temporary Windows test job to diagnose it.

### D6 — Release notes auto-generated from commits

**Chosen:** `generate_release_notes: true` in the `softprops/action-gh-release`
action, which uses GitHub's built-in release note generation (commit messages
between tags).

**Why:** Commit messages in this project are descriptive and conventional. No
additional tooling (conventional-commits, semantic-release) is needed.

## Risks / Trade-offs

- **[PortAudio DLL path changes across sounddevice versions]** → The spec
  resolves the DLL path dynamically via `import sounddevice` at spec-evaluation
  time (`sys._MEIPASS`-based resolution). If sounddevice restructures its data
  package, the spec must be updated. Mitigation: pin `sounddevice` version in CI.

- **[numpy OpenBLAS DLL is 19 MB, exe ~60 MB total]** → Acceptable for a
  desktop app. No mitigation — stripping numpy.libs causes import errors.

- **[Antivirus false positives]** → PyInstaller-packed executables are sometimes
  flagged. UPX is disabled to reduce this risk. No further mitigation is possible
  without code-signing.

- **[`test_multiclient_ptt` flakiness]** → This test starts a real server
  subprocess and is sensitive to port availability. If it fails in CI and blocks
  releases, add `@unittest.skip` with a tracking comment rather than deleting
  the test. See `deploy/windows-build-warnings.md`.

- **[Double-click launches cmd.exe that closes on exit]** → Users who
  double-click the `.exe` from Explorer see the app launch in a temporary
  cmd.exe that closes on exit. The GitHub Release description will document
  that the app should be run from Windows Terminal.

## Migration Plan

No migration required — this is a purely additive change. Existing users running
from source are unaffected. The first tagged release after this change merges
will produce the first `.exe`.

**To cut a release:**
1. Ensure all tests pass on `master`
2. `git tag v0.3.0 && git push origin v0.3.0`
3. GitHub Actions builds and publishes automatically

**To roll back a bad release:** Delete the GitHub Release and tag via the GitHub
UI. No server-side state is affected.

## Open Questions

None. All decisions are resolved.
