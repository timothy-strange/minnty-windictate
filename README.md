# minnty-windictate

Windows 11 port of the Minnty dictation workflow.

## Status

This repo now has a working Windows MVP for configuration, microphone discovery, one-shot recording, local transcription, optional text injection, and a persistent `toggle` / `cancel` recording flow. Persistent loaded-model sessions and a console UI are still in progress.

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
minnty-windictate config
minnty-windictate devices
minnty-windictate listen-once
minnty-windictate toggle
minnty-windictate cancel
minnty-windictate version
```

Useful examples:

```powershell
minnty-windictate config --record-seconds 10 --hotkey ctrl+alt+r
minnty-windictate devices
minnty-windictate listen-once --seconds 6
minnty-windictate listen-once --seconds 6 --type
minnty-windictate toggle
minnty-windictate toggle
minnty-windictate cancel
minnty-windictate cleanup
```

What each command does:

- `doctor`: check Windows prerequisites and Python runtime modules
- `config`: show resolved paths and settings, or save new defaults
- `devices`: list available input devices from `sounddevice`
- `listen-once`: record once to WAV, transcribe locally, and print the result
- `toggle`: start background recording, then stop/transcribe/type on the next call
- `cancel`: stop the current background recording and discard its audio
- `cleanup`: remove app-owned temporary runtime artifacts
- `version`: show the package version

Useful while iterating:

```powershell
ruff format src tests
ruff check . --fix
python -m pip install -e ".[win,dev]"
```
