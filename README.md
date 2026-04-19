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
minnty-windictate listen-once
minnty-windictate console
minnty-windictate run
minnty-windictate stop
minnty-windictate status
minnty-windictate toggle
minnty-windictate cancel
minnty-windictate session-start
minnty-windictate session-status
minnty-windictate session-stop
minnty-windictate version
```

Useful examples:

```powershell
minnty-windictate
minnty-windictate config --record-seconds 10 --hotkey ctrl+alt+r
minnty-windictate devices
minnty-windictate console
minnty-windictate stop
minnty-windictate status
minnty-windictate listen-once --seconds 6
minnty-windictate listen-once --seconds 6 --type
minnty-windictate session-start
minnty-windictate session-status
minnty-windictate toggle
minnty-windictate toggle
minnty-windictate cancel
minnty-windictate session-stop
minnty-windictate cleanup
```

What each command does:

- `minnty-windictate` with no command starts the resident background service
- `doctor`: check Windows prerequisites and Python runtime modules
- `config`: show resolved paths and settings, or save new defaults
- `devices`: list available input devices from `sounddevice`
- `listen-once`: ask the resident service to record once and transcribe
- `console`: open the interactive console UI
- `run`: alias for starting the resident background service
- `stop`: stop the resident background service explicitly
- `status`: show the current resident, recording, and model session state
- `toggle`: start recording, then stop/transcribe/type on the next call through the resident service
- `cancel`: stop the current recording and discard its audio through the resident service
- `session-start`: load the Whisper model inside the resident service
- `session-status`: show whether the model is loaded inside the resident service
- `session-stop`: unload the model inside the resident service
- `cleanup`: remove app-owned temporary runtime artifacts
- `version`: show the package version

Notifications:

- The app emits Windows toast notifications for recording start, stop, cancellation, session startup, session shutdown, transcription completion, cleanup, and command errors when `win10toast` is available.
- If toast notifications are unavailable, it falls back to stderr messages.

Console mode:

- Launch `minnty-windictate console` to open the interactive console.
- Press `t` to start recording, or stop and transcribe when already recording.
- Press `c` to cancel the current recording.
- Press `m` to load or unload the Whisper model inside the resident service.
- Press `r` to refresh the status view.
- Press `q` to quit the console.

Model location:

- By default the app expects a local faster-whisper model under `%USERPROFILE%\Documents\whisper\faster-whisper-large-v3`.
- On this machine that resolves to `C:\Users\danhu\Documents\whisper\faster-whisper-large-v3`.
- Override it with `MINNTY_WINDICTATE_MODEL` if you want to point at a different local model directory.

Resident hotkey mode:

- Run `minnty-windictate` or `minnty-windictate run` to keep the app alive in the background.
- It registers the saved global hotkey from `config`, defaulting to `ctrl+alt+r`.
- Press the hotkey once to start recording and again to stop, transcribe, and type.
- The resident service is a background Python process, so the launching command returns after startup.
- Stop it with `minnty-windictate stop`.

Useful while iterating:

```powershell
ruff format src tests
ruff check . --fix
python -m pip install -e ".[win,dev]"
```
