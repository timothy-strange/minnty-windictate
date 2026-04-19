# minnty-windictate

Windows 11 port of the Minnty dictation workflow.

## Status

This repo now has a working Windows MVP for configuration, microphone discovery, one-shot recording, local transcription, optional text injection, lightweight notifications/status reporting, an interactive console mode, and a resident service that owns the hotkey listener, recording, and loaded Whisper model.

## Purpose

The target workflow is:

1. Hold or press a global hotkey
2. Capture microphone audio on Windows 11
3. Transcribe it locally with Whisper
4. Insert the resulting text into the focused app

## Windows 11 Setup

Install the required system tools in PowerShell:

```powershell
winget install Python.Python.3.12
winget install Git.Git
```

Restart PowerShell after installation, then verify:

```powershell
python --version
git --version
```

## Install

Run these commands from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[win,dev]"
```

If PowerShell blocks virtualenv activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Commands

```powershell
pytest
ruff check .
ruff format --check src tests
minnty-windictate doctor
minnty-windictate
minnty-windictate config
minnty-windictate devices
minnty-windictate stop
minnty-windictate status
minnty-windictate version
```

Useful examples:

```powershell
minnty-windictate
minnty-windictate config --record-seconds 10 --hotkey ctrl+alt+r
minnty-windictate devices
minnty-windictate stop
minnty-windictate status
minnty-windictate cleanup
```

What each command does:

- `minnty-windictate` with no command opens the interactive console UI
- `doctor`: check Windows prerequisites and Python runtime modules
- `config`: show resolved paths and settings, or save new defaults
- `devices`: list available input devices from `sounddevice`
- `stop`: stop the runtime service if it is still running
- `status`: show the current resident, recording, and model session state
- `cleanup`: remove app-owned temporary runtime artifacts
- `version`: show the package version

Notifications:

- The app emits Windows toast notifications for recording start, stop, cancellation, session startup, session shutdown, transcription completion, cleanup, and command errors when `win10toast` is available.
- If toast notifications are unavailable, it falls back to stderr messages.

Console mode:

- Launch `minnty-windictate` to open the interactive console.
- Press `m` to start the local session and load the model.
- Press `c` to cancel current work when recording or transcribing.
- Press `h` to toggle the history view.
- Press `s` to toggle the settings view.
- In settings, press `1` to toggle saving transcriptions to file.
- Press `q` to quit the console.
- Opening the console starts the runtime service automatically.
- Quitting the console unloads the session and stops the service automatically.

Model location:

- By default the app expects a local faster-whisper model under `%USERPROFILE%\Documents\whisper\faster-whisper-large-v3`.
- On this machine that resolves to `C:\Users\danhu\Documents\whisper\faster-whisper-large-v3`.
- Override it with `MINNTY_WINDICTATE_MODEL` if you want to point at a different local model directory.

Resident hotkey mode:

- Run `minnty-windictate` to keep the app active while that console window is open.
- It registers the saved toggle hotkey from `config`, defaulting to `ctrl+alt+space`.
- It also registers a cancel hotkey, defaulting to `ctrl+alt+backspace`.
- Press the toggle hotkey once to start recording and again to stop, transcribe, and type.
- Press the cancel hotkey to discard the current recording.
- The runtime service exists only while the console session is active.
- If the console exits, the service is stopped.

History and settings:

- The console history shows recent actions, errors, and transcription summaries with timestamps.
- When `Save transcriptions to file` is enabled, successful transcriptions are appended under `Documents\transcriber\transcription-YYYY-MM.txt`.

Useful while iterating:

```powershell
ruff format src tests
ruff check . --fix
python -m pip install -e ".[win,dev]"
```
