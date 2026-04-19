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


def _current_hotkeys() -> tuple[str, str]:
    settings = read_settings()
    return settings.hotkey, settings.cancel_hotkey


def _service_status(*, autostart: bool) -> dict:
    hotkey, cancel_hotkey = _current_hotkeys()
    return send_service_command(
        "status",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=autostart,
    )


def _status_report() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    if not service_is_running():
        return "\n".join(
            [
                "resident: idle",
                "recording: idle",
                "session: idle",
                f"latest_wav: {LATEST_WAV_PATH}",
                f"hotkey: {hotkey}",
                f"cancel_hotkey: {cancel_hotkey}",
            ]
        )
    try:
        status = _service_status(autostart=False)
    except RuntimeError:
        return "\n".join(
            [
                "resident: idle",
                "recording: idle",
                "session: idle",
                f"latest_wav: {LATEST_WAV_PATH}",
                f"hotkey: {hotkey}",
                f"cancel_hotkey: {cancel_hotkey}",
            ]
        )
    recording = str(status.get("recording_status", "idle"))
    session = str(status.get("session_status", "idle"))
    return "\n".join(
        [
            "resident: running",
            f"recording: {recording}",
            f"session: {session}",
            f"latest_wav: {status.get('latest_wav', LATEST_WAV_PATH)}",
            f"hotkey: {status.get('hotkey', hotkey)}",
            f"cancel_hotkey: {status.get('cancel_hotkey', cancel_hotkey)}",
        ]
    )


def _recording_active() -> bool:
    if not service_is_running():
        return False
    try:
        return str(_service_status(autostart=False).get("recording_status", "idle")) == "recording"
    except RuntimeError:
        return False


def _session_ready() -> bool:
    if not service_is_running():
        return False
    try:
        return str(_service_status(autostart=False).get("session_status", "idle")) != "idle"
    except RuntimeError:
        return False


def _run_hotkeys() -> None:
    hotkey, cancel_hotkey = _current_hotkeys()
    state = start_service(hotkey, cancel_hotkey)
    print(f"Resident service running on port {state.port}")


def _stop_hotkeys() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    return stop_service(hotkey, cancel_hotkey)


def _start_session() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    response = send_service_command(
        "session-start",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=True,
    )
    return str(response.get("message", "Session ready"))


def _stop_session() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    response = send_service_command(
        "session-stop",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=False,
    )
    return str(response.get("message", "Session stopped"))


def _run_console() -> None:
    _run_hotkeys()
    try:
        run_console(
            status_snapshot=_console_status_snapshot,
            execute_action=_console_execute_action,
            toggle_setting=_toggle_setting,
        )
    finally:
        _stop_hotkeys()


def _console_status_snapshot() -> dict[str, object]:
    settings = read_settings()
    if not service_is_running():
        return {
            "recording_status": "idle",
            "session_status": "idle",
            "status_line": "Idle",
            "last_transcription_line": "None",
            "history": [],
            "save_transcriptions_to_file": settings.save_transcriptions_to_file,
        }
    try:
        status = _service_status(autostart=False)
    except RuntimeError as exc:
        return {
            "recording_status": "idle",
            "session_status": "idle",
            "status_line": f"Error: {exc}",
            "last_transcription_line": "None",
            "history": [],
            "save_transcriptions_to_file": settings.save_transcriptions_to_file,
        }
    recording = str(status.get("recording_status", "idle"))
    session = str(status.get("session_status", "idle"))
    if session == "loading":
        status_line = "Loading model..."
    elif recording == "recording":
        status_line = "Recording"
    elif recording == "transcribing":
        status_line = "Transcribing..."
    else:
        status_line = "Idle"
    return {
        "recording_status": recording,
        "session_status": session,
        "status_line": status_line,
        "last_transcription_line": str(status.get("last_transcription_line", "None")),
        "history": list(status.get("history", [])),
        "save_transcriptions_to_file": settings.save_transcriptions_to_file,
    }


def _console_execute_action(action: str) -> str:
    if action == "start-session":
        return _start_session()
    if action in {"cancel", "cancel-recording"}:
        return _cancel()
    if action in {"end-session", "session-stop"}:
        return _stop_session()
    raise RuntimeError(f"Unsupported console action: {action}")


def _toggle_setting(name: str) -> bool:
    settings = read_settings()
    if name != "save_transcriptions_to_file":
        raise RuntimeError(f"Unknown setting: {name}")
    updated = update_settings(save_transcriptions_to_file=not settings.save_transcriptions_to_file)
    return updated.save_transcriptions_to_file


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
        hotkey, cancel_hotkey = _current_hotkeys()
        stop_service(hotkey, cancel_hotkey)
    except RuntimeError:
        pass
    for path in (LATEST_WAV_PATH, SESSION_STATE_PATH):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if not removed:
        return "Nothing to clean up."
    return "Removed:\n" + "\n".join(removed)


def _toggle() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    response = send_service_command(
        "toggle",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=False,
    )
    return str(response.get("message", ""))


def _cancel() -> str:
    hotkey, cancel_hotkey = _current_hotkeys()
    response = send_service_command(
        "cancel",
        hotkey=hotkey,
        cancel_hotkey=cancel_hotkey,
        autostart=False,
    )
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
    config_parser.add_argument("--cancel-hotkey", help="Saved hotkey for cancelling a recording")
    config_parser.add_argument("--auto-paste", dest="auto_paste", action="store_true", help="Save auto-paste as enabled")
    config_parser.add_argument("--no-auto-paste", dest="auto_paste", action="store_false", help="Save auto-paste as disabled")
    config_parser.set_defaults(auto_paste=None)
    subparsers.add_parser("devices", help="List available microphone input devices")
    subparsers.add_parser("stop", help="Stop the console-owned service if it is still running")
    subparsers.add_parser("status", help="Show current resident, recording, and session status")
    subparsers.add_parser("cleanup", help="Remove local runtime artifacts")
    service = subparsers.add_parser("service", help=argparse.SUPPRESS)
    service.add_argument("--port", required=True, type=int)
    service.add_argument("--token", required=True)
    service.add_argument("--hotkey", required=True)
    service.add_argument("--cancel-hotkey", required=True)
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
            ("cancel_hotkey", "cancel_hotkey"),
            ("auto_paste", "auto_paste"),
        ):
            value = getattr(args, arg_name)
            if value is not None:
                changes[setting_name] = value
        if changes:
            updated = update_settings(**changes)
            if ("hotkey" in changes or "cancel_hotkey" in changes) and service_is_running():
                start_service(updated.hotkey, updated.cancel_hotkey)
        print(_config_report())
        return
    if args.command == "devices":
        print(format_input_devices(list_input_devices()))
        return
    if args.command == "stop":
        print(_stop_hotkeys())
        return
    if args.command == "status":
        print(_status_report())
        return
    if args.command == "cleanup":
        message = _cleanup()
        notify(APP_NAME, "Cleanup complete")
        print(message)
        return
    if args.command == "service":
        ensure_directories()
        serve_resident_service(
            port=args.port,
            token=args.token,
            hotkey=args.hotkey,
            cancel_hotkey=args.cancel_hotkey,
        )
        return
    if args.command == "version":
        print(__version__)
        return

    parser.print_help()
