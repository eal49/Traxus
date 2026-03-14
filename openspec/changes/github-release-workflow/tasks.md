## 1. PyInstaller Spec

- [x] 1.1 Create `traxus.spec` at the repo root — `Analysis` entry point is `client/main.py`; set `console=True`, `upx=False`, `name='traxus'`
- [x] 1.2 In `traxus.spec`, add `datas` entry to bundle `client/app.tcss` into the `client/` subdirectory of the archive (`('client/app.tcss', 'client')`)
- [x] 1.3 In `traxus.spec`, dynamically locate the sounddevice PortAudio DLL via `import sounddevice` and add it to `binaries` — bundle `libportaudio64bit.dll` into `_sounddevice_data/portaudio-binaries/`
- [x] 1.4 In `traxus.spec`, add `hiddenimports` for websockets submodules: `websockets.asyncio.client`, `websockets.asyncio.server`, `websockets.exceptions`
- [x] 1.5 In `traxus.spec`, add `collect_data('textual')` to the `datas` list so Textual's tree-sitter highlight files are included
- [x] 1.6 Test the spec locally: `pip install pyinstaller` then `pyinstaller traxus.spec` — verify `dist/traxus.exe` launches and shows the login screen

## 2. GitHub Actions Workflow

- [x] 2.1 Create `.github/workflows/release.yml` with trigger `on: push: tags: ['v*.*.*']`
- [x] 2.2 Add `test` job on `ubuntu-latest`, Python 3.12: `pip install textual websockets numpy` then `python -m unittest discover -s tests -v`
- [x] 2.3 Add `build-windows` job on `windows-latest`, Python 3.13: `pip install textual websockets sounddevice numpy pyinstaller` then `pyinstaller traxus.spec`
- [x] 2.4 In `build-windows`, rename the output before uploading: `mv dist/traxus.exe dist/traxus-${{ github.ref_name }}-windows.exe`
- [x] 2.5 In `build-windows`, upload the renamed exe as a workflow artifact using `actions/upload-artifact@v4`
- [x] 2.6 Add `release` job with `needs: [test, build-windows]` on `ubuntu-latest`; grant `permissions: contents: write`
- [x] 2.7 In `release`, download the artifact with `actions/download-artifact@v4` then create the GitHub Release with `softprops/action-gh-release@v2`, attaching the `.exe` and setting `generate_release_notes: true`

## 3. Verification

- [ ] 3.1 Push a test tag (e.g. `v0.0.1-test`) to a non-main branch or fork and confirm all three jobs complete successfully and the release asset appears
- [ ] 3.2 Download the released `.exe`, run it from Windows Terminal, connect to a local server, and confirm PTT audio works (`AUDIO_AVAILABLE` is `True`)
- [ ] 3.3 Delete the test tag and release after verification
