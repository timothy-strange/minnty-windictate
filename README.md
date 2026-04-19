# minnty-windictate

Windows 11 port of the Minnty dictation workflow.

## Status

This repo now has a working Windows MVP for configuration, microphone discovery, one-shot recording, local transcription, optional text injection, a persistent `toggle` / `cancel` recording flow, a reusable background Whisper session, lightweight Windows notifications/status reporting, and an interactive console mode.

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
winget install Gyan.FFmpeg
winget install Git.Git
```

Restart PowerShell after installation, then verify:

```powershell
python --version
ffmpeg -version
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

- `minnty-windictate` with no command opens the interactive console UI
- `doctor`: check Windows prerequisites and Python runtime modules
- `config`: show resolved paths and settings, or save new defaults
- `devices`: list available input devices from `sounddevice`
- `listen-once`: record once to WAV, transcribe locally, and print the result
- `status`: show the current recording/session state and latest WAV path
- `toggle`: start background recording, then stop/transcribe/type on the next call
- `cancel`: stop the current background recording and discard its audio
- `session-start`: load the Whisper model into a reusable background process
- `session-status`: show whether the reusable session is running
- `session-stop`: stop the reusable background session
- `cleanup`: remove app-owned temporary runtime artifacts
- `version`: show the package version

Notifications:

- The app emits Windows toast notifications for recording start, stop, cancellation, session startup, session shutdown, transcription completion, cleanup, and command errors when `win10toast` is available.
- If toast notifications are unavailable, it falls back to stderr messages.

Console mode:

- Launch `minnty-windictate` with no command to open the interactive console.
- Press `t` to start recording, or stop and transcribe when already recording.
- Press `c` to cancel the current recording.
- Press `m` to start or stop the reusable Whisper session.
- Press `r` to refresh the status view.
- Press `q` to quit the console.

Useful while iterating:

```powershell
ruff format src tests
ruff check . --fix
python -m pip install -e ".[win,dev]"
```
