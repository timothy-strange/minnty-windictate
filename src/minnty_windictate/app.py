from __future__ import annotations

import argparse
from dataclasses import asdict

from . import __version__
from .audio import format_input_devices, list_input_devices
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
    ensure_directories,
    session_config,
)
from .environment import environment_checks, format_checks
from .notify import APP_NAME, notify
from .service_process import serve as serve_resident_service
from .service_runtime import send_service_command, service_is_running, start_service, stop_service
from .settings import read_settings, update_settings


def _service_status(*, autostart: bool) -> dict:
    return send_service_command("status", hotkey=read_settings().hotkey, autostart=autostart)


def _status_report() -> str:
    hotkey = read_settings().hotkey
    if not service_is_running():
        return "\n".join(
            [
                "resident: idle",
                "recording: idle",
                "session: idle",
                f"latest_wav: {LATEST_WAV_PATH}",
                f"hotkey: {hotkey}",
            ]
        )
    status = _service_status(autostart=False)
    recording = "recording" if status.get("recording") else "idle"
    session = "ready" if status.get("session") else "idle"
    return "\n".join(
        [
            "resident: running",
            f"recording: {recording}",
            f"session: {session}",
            f"latest_wav: {status.get('latest_wav', LATEST_WAV_PATH)}",
            f"hotkey: {status.get('hotkey', hotkey)}",
        ]
    )


def _recording_active() -> bool:
    if not service_is_running():
        return False
    return bool(_service_status(autostart=False).get("recording"))


def _session_ready() -> bool:
    if not service_is_running():
        return False
    return bool(_service_status(autostart=False).get("session"))


def _run_hotkeys() -> None:
    state = start_service(read_settings().hotkey)
    print(f"Resident service running on port {state.port}")


def _stop_hotkeys() -> str:
    return stop_service(read_settings().hotkey)


def _start_session() -> str:
    response = send_service_command("session-start", hotkey=read_settings().hotkey, autostart=True)
    return str(response.get("message", "Session ready"))


def _stop_session() -> str:
    response = send_service_command("session-stop", hotkey=read_settings().hotkey, autostart=False)
    return str(response.get("message", "Session stopped"))


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
        f"session_running: {service_is_running()}",
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
    try:
        stop_service(read_settings().hotkey)
    except RuntimeError:
        pass
    for path in (LATEST_WAV_PATH, RECORDING_STATE_PATH, SESSION_STATE_PATH):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if not removed:
        return "Nothing to clean up."
    return "Removed:\n" + "\n".join(removed)


def _listen_once(*, seconds: float | None, device: str | int | None, sample_rate: int | None, should_type: bool) -> str:
    response = send_service_command(
        "listen-once",
        hotkey=read_settings().hotkey,
        autostart=True,
        seconds=seconds,
        device=None if device is None else str(device),
        sample_rate=sample_rate,
        should_type=should_type,
    )
    return str(response.get("text", ""))


def _toggle() -> str:
    response = send_service_command("toggle", hotkey=read_settings().hotkey, autostart=True)
    return str(response.get("message", ""))


def _cancel() -> str:
    response = send_service_command("cancel", hotkey=read_settings().hotkey, autostart=False)
    return str(response.get("message", ""))


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
    config_parser.add_argument("--auto-paste", dest="auto_paste", action="store_true", help="Save auto-paste as enabled")
    config_parser.add_argument("--no-auto-paste", dest="auto_paste", action="store_false", help="Save auto-paste as disabled")
    config_parser.set_defaults(auto_paste=None)
    subparsers.add_parser("devices", help="List available microphone input devices")
    listen_once = subparsers.add_parser("listen-once", help="Record once and transcribe")
    listen_once.add_argument("--seconds", type=float, help="Recording duration in seconds")
    listen_once.add_argument("--device", help="Input device name or index")
    listen_once.add_argument("--sample-rate", type=int, help="Recording sample rate")
    listen_once.add_argument("--type", action="store_true", help="Type the transcript into the focused app after transcription")
    subparsers.add_parser("run", help="Start resident global hotkey mode")
    subparsers.add_parser("stop", help="Stop the resident background service")
    subparsers.add_parser("console", help="Open the interactive console UI")
    subparsers.add_parser("status", help="Show current resident, recording, and session status")
    subparsers.add_parser("toggle", help="Start recording, or stop and transcribe")
    subparsers.add_parser("cancel", help="Cancel the current recording")
    subparsers.add_parser("session-start", help="Load the model inside the resident service")
    subparsers.add_parser("session-stop", help="Unload the model inside the resident service")
    subparsers.add_parser("session-status", help="Show whether the model is loaded in the resident service")
    subparsers.add_parser("cleanup", help="Remove local runtime artifacts")
    service = subparsers.add_parser("service", help=argparse.SUPPRESS)
    service.add_argument("--port", required=True, type=int)
    service.add_argument("--token", required=True)
    service.add_argument("--hotkey", required=True)
    subparsers.add_parser("version", help="Show version")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        _run_hotkeys()
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
    if args.command == "run":
        _run_hotkeys()
        return
    if args.command == "stop":
        print(_stop_hotkeys())
        return
    if args.command == "console":
        _run_console()
        return
    if args.command == "status":
        print(_status_report())
        return
    if args.command == "listen-once":
        try:
            print(_listen_once(seconds=args.seconds, device=args.device, sample_rate=args.sample_rate, should_type=args.type))
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
        print("ready" if _session_ready() else "idle")
        return
    if args.command == "cleanup":
        message = _cleanup()
        notify(APP_NAME, "Cleanup complete")
        print(message)
        return
    if args.command == "service":
        ensure_directories()
        serve_resident_service(port=args.port, token=args.token, hotkey=args.hotkey)
        return
    if args.command == "version":
        print(__version__)
        return

    parser.print_help()
