## Why

There is currently no automated way to distribute Traxus to end users — they must
clone the repository and install Python manually. A GitHub Actions release workflow
triggered by version tags will produce a self-contained Windows `.exe` that anyone
can download and run without any prerequisites.

## What Changes

- Add `.github/workflows/release.yml` — tag-triggered CI/CD workflow with three
  jobs: test (Linux), build-windows (Windows .exe via PyInstaller), and release
  (create GitHub Release and attach the binary).
- Add `traxus.spec` — PyInstaller build specification for the Windows client
  executable, bundling all native DLLs (PortAudio, numpy/OpenBLAS) and the
  Textual CSS file.
- Add `deploy/windows-build-warnings.md` — already exists; referenced by this
  change as the authoritative gotcha list for build maintainers.

## Capabilities

### New Capabilities

- `windows-exe-release`: Tag-triggered GitHub Actions workflow that builds and
  publishes a self-contained Windows `.exe` of the Traxus client with full audio
  (PTT/VAD) support, attached to a GitHub Release with auto-generated release notes.

### Modified Capabilities

<!-- None — no existing spec-level behaviour changes. -->

## Impact

- **New files:** `.github/workflows/release.yml`, `traxus.spec`
- **Existing file referenced:** `deploy/windows-build-warnings.md`
- **No changes to server, shared, or client source code**
- **No new runtime dependencies** — `pyinstaller` is a build-only tool
- **Build Python version:** 3.13 (GitHub Actions constraint; codebase is compatible)
- **Expected artifact size:** 50–70 MB `.exe` (dominated by numpy OpenBLAS DLL)
- **Trigger:** pushing a tag matching `v*.*.*` to the `master` branch
