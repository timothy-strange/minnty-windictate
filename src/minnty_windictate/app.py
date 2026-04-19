from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .audio import format_input_devices, list_input_devices, record_wav
from .console import run_console
from .config import (
    CACHE_DIR,
    CONFIG_DIR,
    DATA_DIR,
    LATEST_WAV_PATH,
    RECORD_DIR,
    RECORDING_STATE_PATH,
    RUNTIME_DIR,
    SETTINGS_STATE_PATH,
    SESSION_STATE_PATH,
    SessionConfig,
    ensure_directories,
    session_config,
)
from .environment import environment_checks, format_checks
from .notify import APP_NAME, notify
from .recording_state import (
    RecordingState,
    clear_recording_state,
    process_is_running,
    read_recording_state,
    write_recording_state,
)
from .recorder_process import record_until_stopped
from .session_runtime import (
    read_session_state,
    session_is_running,
    start_session_server,
    stop_session_server,
    transcribe_via_session,
)
from .session_server import serve_session
from .settings import read_settings, update_settings
from .typing import type_text


def _status_report() -> str:
    recording_state = read_recording_state(RECORDING_STATE_PATH)
    session_state = read_session_state()
    recording = "recording" if recording_state and process_is_running(recording_state.pid) else "idle"
    session = "ready" if session_state and session_is_running() else "idle"
    return "\n".join(
        [
            f"recording: {recording}",
            f"session: {session}",
            f"latest_wav: {LATEST_WAV_PATH}",
        ]
    )


def _recording_active() -> bool:
    state = read_recording_state(RECORDING_STATE_PATH)
    return state is not None and process_is_running(state.pid)


def _session_ready() -> bool:
    return session_is_running()


def _start_session() -> str:
    state = start_session_server(session_config())
    notify(APP_NAME, "Transcription session ready")
    return f"Session ready on port {state.port}"


def _stop_session() -> str:
    message = stop_session_server()
    notify(APP_NAME, message)
    return message


def _run_console() -> None:
    run_console(
        status_report=_status_report,
        toggle=_toggle,
        cancel=_cancel,
        session_start=_start_session,
        session_stop=_stop_session,
        is_recording_active=_recording_active,
        is_session_ready=_session_ready,
    )


def _config_report() -> str:
    settings = read_settings()
    session = session_config()
    lines = [
        f"config_dir: {CONFIG_DIR}",
        f"cache_dir: {CACHE_DIR}",
        f"data_dir: {DATA_DIR}",
        f"record_dir: {RECORD_DIR}",
        f"runtime_dir: {RUNTIME_DIR}",
        f"settings_path: {SETTINGS_STATE_PATH}",
        f"recording_state_path: {RECORDING_STATE_PATH}",
        f"session_state_path: {SESSION_STATE_PATH}",
        f"session_running: {session_is_running()}",
        "session:",
    ]
    for key, value in asdict(session).items():
        lines.append(f"  {key}: {value}")
    lines.append("settings:")
    for key, value in asdict(settings).items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _cleanup() -> str:
    removed: list[str] = []
    state = read_recording_state(RECORDING_STATE_PATH)
    if state is not None:
        Path(state.stop_path).write_text("stop", encoding="utf-8")
    stop_session_server()
    for path in (LATEST_WAV_PATH, RECORDING_STATE_PATH, SESSION_STATE_PATH):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if not removed:
        return "Nothing to clean up."
    return "Removed:\n" + "\n".join(removed)


def _listen_once(*, seconds: float | None, device: str | int | None, sample_rate: int | None, should_type: bool) -> str:
    ensure_directories()
    settings = read_settings()
    selected_seconds = seconds if seconds is not None else settings.record_seconds
    selected_device = device if device is not None else settings.input_device
    selected_sample_rate = sample_rate if sample_rate is not None else settings.sample_rate

    path = record_wav(
        path=LATEST_WAV_PATH,
        seconds=selected_seconds,
        sample_rate=selected_sample_rate,
        channels=settings.channels,
        device=selected_device,
    )
    session = session_config()
    text = transcribe_via_session(path, session)
    if should_type and settings.auto_paste:
        type_text(text)
    notify(APP_NAME, "Transcription complete")
    return text


def _coerce_device(value: str | int | None) -> str | int | None:
    if isinstance(value, int) or value is None:
        return value
    if value.isdigit():
        return int(value)
    return value


def _recording_stop_path() -> Path:
    return RUNTIME_DIR / "recording.stop"


def _start_background_recording() -> str:
    ensure_directories()
    state = read_recording_state(RECORDING_STATE_PATH)
    if state is not None and process_is_running(state.pid):
        raise RuntimeError("Recording is already active.")
    clear_recording_state(RECORDING_STATE_PATH)

    settings = read_settings()
    stop_path = _recording_stop_path()
    stop_path.unlink(missing_ok=True)

    command = [
        sys.executable,
        "-m",
        "minnty_windictate.cli",
        "record-background",
        "--output",
        str(LATEST_WAV_PATH),
        "--stop-path",
        str(stop_path),
        "--sample-rate",
        str(settings.sample_rate),
        "--channels",
        str(settings.channels),
    ]
    if settings.input_device is not None:
        command.extend(["--device", str(settings.input_device)])

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, creationflags=creationflags)
    write_recording_state(
        RECORDING_STATE_PATH,
        RecordingState(
            pid=process.pid,
            path=str(LATEST_WAV_PATH),
            stop_path=str(stop_path),
            started_at=time.time(),
        ),
    )
    notify(APP_NAME, "Recording started")
    return "Recording started"


def _wait_for_process_exit(pid: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process_is_running(pid):
            return
        time.sleep(0.1)
    raise RuntimeError("Recorder process did not stop in time.")


def _finish_recording(*, should_type: bool) -> str:
    state = read_recording_state(RECORDING_STATE_PATH)
    if state is None:
        raise RuntimeError("No active recording to stop.")
    if not process_is_running(state.pid):
        clear_recording_state(RECORDING_STATE_PATH)
        raise RuntimeError("Recording is no longer active.")

    stop_path = Path(state.stop_path)
    stop_path.write_text("stop", encoding="utf-8")
    _wait_for_process_exit(state.pid)
    clear_recording_state(RECORDING_STATE_PATH)
    stop_path.unlink(missing_ok=True)

    session = session_config()
    text = transcribe_via_session(Path(state.path), session)
    settings = read_settings()
    if should_type and settings.auto_paste:
        type_text(text)
    notify(APP_NAME, "Recording stopped and transcribed")
    return text


def _toggle() -> str:
    state = read_recording_state(RECORDING_STATE_PATH)
    if state is not None and process_is_running(state.pid):
        return _finish_recording(should_type=True)
    return _start_background_recording()


def _cancel() -> str:
    state = read_recording_state(RECORDING_STATE_PATH)
    if state is None:
        raise RuntimeError("No active recording to cancel.")
    stop_path = Path(state.stop_path)
    stop_path.write_text("stop", encoding="utf-8")
    if process_is_running(state.pid):
        _wait_for_process_exit(state.pid)
    clear_recording_state(RECORDING_STATE_PATH)
    stop_path.unlink(missing_ok=True)
    Path(state.path).unlink(missing_ok=True)
    notify(APP_NAME, "Recording cancelled")
    return "Recording cancelled"


def _record_background(
    *,
    output: str,
    stop_path: str,
    sample_rate: int,
    channels: int,
    device: str | int | None,
) -> None:
    record_until_stopped(
        path=Path(output),
        stop_path=Path(stop_path),
        sample_rate=sample_rate,
        channels=channels,
        device=_coerce_device(device),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minnty-windictate")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Check Windows runtime prerequisites")
    config_parser = subparsers.add_parser("config", help="Show or update config and settings")
    config_parser.add_argument("--input-device", help="Saved input device name or index")
    config_parser.add_argument("--sample-rate", type=int, help="Saved sample rate")
    config_parser.add_argument("--channels", type=int, help="Saved channel count")
    config_parser.add_argument("--record-seconds", type=float, help="Saved recording length")
    config_parser.add_argument("--hotkey", help="Saved hotkey for resident mode")
    config_parser.add_argument(
        "--auto-paste",
        dest="auto_paste",
        action="store_true",
        help="Save auto-paste as enabled",
    )
    config_parser.add_argument(
        "--no-auto-paste",
        dest="auto_paste",
        action="store_false",
        help="Save auto-paste as disabled",
    )
    config_parser.set_defaults(auto_paste=None)
    subparsers.add_parser("devices", help="List available microphone input devices")
    listen_once = subparsers.add_parser("listen-once", help="Record once and transcribe")
    listen_once.add_argument("--seconds", type=float, help="Recording duration in seconds")
    listen_once.add_argument("--device", help="Input device name or index")
    listen_once.add_argument("--sample-rate", type=int, help="Recording sample rate")
    listen_once.add_argument(
        "--type",
        action="store_true",
        help="Type the transcript into the focused app after transcription",
    )
    subparsers.add_parser("status", help="Show current recording and session status")
    subparsers.add_parser("toggle", help="Start recording, or stop and transcribe")
    subparsers.add_parser("cancel", help="Cancel the current recording")
    subparsers.add_parser("session-start", help="Start the persistent transcription session")
    subparsers.add_parser("session-stop", help="Stop the persistent transcription session")
    subparsers.add_parser("session-status", help="Show transcription session status")
    subparsers.add_parser("cleanup", help="Remove local runtime artifacts")
    background = subparsers.add_parser("record-background", help=argparse.SUPPRESS)
    background.add_argument("--output", required=True)
    background.add_argument("--stop-path", required=True)
    background.add_argument("--sample-rate", required=True, type=int)
    background.add_argument("--channels", required=True, type=int)
    background.add_argument("--device")
    session_server = subparsers.add_parser("session-server", help=argparse.SUPPRESS)
    session_server.add_argument("--port", required=True, type=int)
    session_server.add_argument("--token", required=True)
    session_server.add_argument("--model-name", required=True)
    session_server.add_argument("--device", required=True)
    session_server.add_argument("--compute-type", required=True)
    session_server.add_argument("--beam-size", required=True, type=int)
    session_server.add_argument("--language")
    subparsers.add_parser("version", help="Show version")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        _run_console()
        return
    if args.command == "doctor":
        print(format_checks(environment_checks()))
        return
    if args.command == "config":
        changes: dict[str, object] = {}
        for arg_name, setting_name in (
            ("input_device", "input_device"),
            ("sample_rate", "sample_rate"),
            ("channels", "channels"),
            ("record_seconds", "record_seconds"),
            ("hotkey", "hotkey"),
            ("auto_paste", "auto_paste"),
        ):
            value = getattr(args, arg_name)
            if value is not None:
                changes[setting_name] = value
        if changes:
            update_settings(**changes)
        print(_config_report())
        return
    if args.command == "devices":
        print(format_input_devices(list_input_devices()))
        return
    if args.command == "status":
        print(_status_report())
        return
    if args.command == "listen-once":
        try:
            print(
                _listen_once(
                    seconds=args.seconds,
                    device=args.device,
                    sample_rate=args.sample_rate,
                    should_type=args.type,
                )
            )
        except Exception as exc:
            notify(f"{APP_NAME} error", str(exc))
            raise
        return
    if args.command == "toggle":
        try:
            print(_toggle())
        except Exception as exc:
            notify(f"{APP_NAME} error", str(exc))
            raise
        return
    if args.command == "cancel":
        try:
            print(_cancel())
        except Exception as exc:
            notify(f"{APP_NAME} error", str(exc))
            raise
        return
    if args.command == "session-start":
        print(_start_session())
        return
    if args.command == "session-stop":
        print(_stop_session())
        return
    if args.command == "session-status":
        state = read_session_state()
        if state is None or not session_is_running():
            print("idle")
            return
        print("ready")
        return
    if args.command == "cleanup":
        message = _cleanup()
        notify(APP_NAME, "Cleanup complete")
        print(message)
        return
    if args.command == "record-background":
        _record_background(
            output=args.output,
            stop_path=args.stop_path,
            sample_rate=args.sample_rate,
            channels=args.channels,
            device=args.device,
        )
        return
    if args.command == "session-server":
        serve_session(
            port=args.port,
            token=args.token,
            session=SessionConfig(
                model_name=args.model_name,
                device=args.device,
                compute_type=args.compute_type,
                beam_size=args.beam_size,
                language=args.language,
            ),
        )
        return
    if args.command == "version":
        print(__version__)
        return

    parser.print_help()
