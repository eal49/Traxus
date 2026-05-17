## Purpose

Define the GitHub Actions release workflow and PyInstaller build requirements for producing self-contained Windows and macOS client binaries.

## Requirements

### Requirement: Release workflow triggers on version tag
The GitHub Actions workflow SHALL trigger automatically when a tag matching
`v*.*.*` is pushed to the repository. No manual workflow dispatch is required
to produce a release.

#### Scenario: Tag push triggers workflow
- **WHEN** a tag matching `v*.*.*` is pushed to `master`
- **THEN** the release workflow starts automatically
- **THEN** all three jobs (test, build-windows, release) are executed in the
  correct dependency order

#### Scenario: Non-tag push does not trigger release
- **WHEN** a commit is pushed to `master` without a matching tag
- **THEN** the release workflow does NOT run

### Requirement: Tests must pass before a release binary is published
The release job SHALL only run after the test job completes successfully.
A failing test suite MUST block the release.

#### Scenario: Failing tests block release
- **WHEN** the test job exits with a non-zero status
- **THEN** the build-windows and release jobs do not run
- **THEN** no GitHub Release is created

#### Scenario: Passing tests allow release to proceed
- **WHEN** the test job exits successfully
- **THEN** the build-windows job runs
- **THEN** if build-windows succeeds, the release job runs

### Requirement: Windows executable includes full audio support
The built `traxus.exe` SHALL include sounddevice and its PortAudio DLL so that
PTT and VAD voice features are available without any additional installation.

#### Scenario: Audio available in built executable
- **WHEN** `traxus.exe` is launched on a Windows machine with no Python installed
- **THEN** `AUDIO_AVAILABLE` is `True` at runtime
- **THEN** the PTT key binding is functional

#### Scenario: Executable runs without Python installed
- **WHEN** `traxus.exe` is launched on a machine with no Python installation
- **THEN** the application starts and shows the login screen

### Requirement: PyInstaller spec is version-controlled
The build specification SHALL be stored as `traxus.spec` at the repository root
so that the build is reproducible locally and auditable via git history.

#### Scenario: Local build reproduces CI output
- **WHEN** a developer runs `pyinstaller traxus.spec` locally with the same
  Python 3.13 environment used in CI
- **THEN** the resulting `dist/traxus.exe` is functionally equivalent to the
  CI-produced binary

### Requirement: GitHub Release is created automatically with release notes
The workflow SHALL create a GitHub Release on every successful tag build,
attach the `.exe` as a release asset, and include auto-generated release notes
derived from commit messages between the previous and current tags.

#### Scenario: Release created on successful build
- **WHEN** both the test and build-windows jobs succeed
- **THEN** a GitHub Release is created for the pushed tag
- **THEN** the release contains `traxus-<version>-windows.exe` as a downloadable asset
- **THEN** the release body contains auto-generated notes from commit history

#### Scenario: Release asset uses versioned filename
- **WHEN** tag `v0.3.0` is pushed
- **THEN** the release asset is named `traxus-v0.3.0-windows.exe`

### Requirement: Packaged binaries include systray icon assets
The Windows `.exe` and macOS binary SHALL include the six PNG files from
`Art/SystrayIcons/` so the system tray icon renders correctly when the
application is run from the packaged binary.

#### Scenario: Icons available in Windows executable
- **WHEN** `traxus.exe` is launched on a Windows machine with no source repo present
- **THEN** `Art/SystrayIcons/*.png` SHALL be resolvable via `sys._MEIPASS / "SystrayIcons"`
- **THEN** the system tray icon SHALL display the correct state image

#### Scenario: Icons available in macOS binary
- **WHEN** the macOS binary is launched without the source repo present
- **THEN** `Art/SystrayIcons/*.png` SHALL be resolvable via `sys._MEIPASS / "SystrayIcons"`
- **THEN** the system tray icon SHALL display the correct state image

#### Scenario: pystray and Pillow bundled in executables
- **WHEN** the PyInstaller spec is used to build the executable
- **THEN** `pystray` and `Pillow` SHALL be included in the bundle
- **THEN** the tray icon SHALL appear without requiring any additional installation
