from __future__ import annotations

import msvcrt
import time
from typing import Callable


def console_available_actions(*, recording_status: str, session_status: str) -> list[tuple[str, str, str]]:
    actions: list[tuple[str, str, str]] = []
    if recording_status == "recording":
        actions.append(("c", "Cancel recording", "cancel-recording"))
    elif session_status == "idle":
        actions.append(("m", "Start session and load model", "start-session"))

    actions.append(("q", "Quit and unload", "quit-console"))
    actions.append(("h", "History", "history"))
    actions.append(("s", "Settings", "settings"))
    return actions


def render_console(*, status_line: str, last_transcription_line: str, actions: list[tuple[str, str, str]]) -> str:
    lines = [
        "\x1b[2J\x1b[HTranscriber",
        f"Status: {status_line}",
        f"Last transcription: {last_transcription_line}",
        "",
        "Available actions:",
    ]
    for key, label, _action in actions:
        lines.append(f"  [{key}] {label}")
    return "\n".join(lines)


def render_history(*, entries: list[dict]) -> str:
    lines = ["\x1b[2J\x1b[HTranscriber", "History (press h or Esc to close)", ""]
    if not entries:
        lines.append("No history yet.")
        return "\n".join(lines)
    for entry in entries:
        parts = [str(entry.get("timestamp", "--:--:--")), str(entry.get("result", "?")).upper(), str(entry.get("action", "event"))]
        if entry.get("message"):
            parts.append(str(entry["message"]))
        if entry.get("word_count") is not None:
            parts.append(f"{entry['word_count']} words")
        if entry.get("audio_duration_s") is not None:
            parts.append(f"audio {entry['audio_duration_s']:.1f}s")
        if entry.get("transcription_duration_s") is not None:
            parts.append(f"transcribe {entry['transcription_duration_s']:.1f}s")
        lines.append(" | ".join(parts))
        if entry.get("text"):
            lines.append(str(entry["text"]))
            lines.append("")
    return "\n".join(lines)


def render_settings(*, save_transcriptions_to_file: bool) -> str:
    return "\n".join(
        [
            "\x1b[2J\x1b[HTranscriber",
            "Settings (press s or Esc to close)",
            "",
            f"[1] Save transcriptions to file: {'On' if save_transcriptions_to_file else 'Off'}",
            "    Saves successful transcriptions to Documents/minnty-windictate/transcriptions/transcription-YYYY-MM.txt",
        ]
    )


def read_key() -> str:
    while True:
        key = msvcrt.getwch().lower()
        if key in {"\x00", "\xe0"}:
            _ignored = msvcrt.getwch()
            continue
        return key


def key_available() -> bool:
    return bool(msvcrt.kbhit())


def feedback_message(*, action: str) -> str:
    if action in {"start-session", "session-start"}:
        return "Loading model..."
    if action in {"cancel", "cancel-recording"}:
        return "Cancelling..."
    if action in {"end-session", "session-stop"}:
        return "Shutting down..."
    return "Working..."


def run_console(
    *,
    status_snapshot: Callable[[], dict[str, object]],
    execute_action: Callable[[str], str],
    toggle_setting: Callable[[str], bool],
    key_available_fn=key_available,
    sleep_fn=time.sleep,
    print_fn=print,
) -> None:
    status_override = ""
    pending_shutdown = False
    show_history = False
    show_settings = False
    last_rendered_snapshot: tuple | None = None

    def snapshot_signature(snapshot: dict[str, object]) -> tuple:
        history = tuple(
            (
                entry.get("timestamp"),
                entry.get("kind"),
                entry.get("action"),
                entry.get("result"),
                entry.get("message"),
                entry.get("text"),
            )
            for entry in list(snapshot.get("history", []))
        )
        if show_history:
            return ("history", history)
        if show_settings:
            return ("settings", snapshot.get("save_transcriptions_to_file"))
        return (
            "main",
            snapshot.get("recording_status"),
            snapshot.get("session_status"),
            snapshot.get("status_line"),
            snapshot.get("last_transcription_line"),
            status_override,
        )

    def redraw(snapshot: dict[str, object] | None = None, *, force: bool = False) -> None:
        nonlocal last_rendered_snapshot
        if snapshot is None:
            snapshot = status_snapshot()
        signature = snapshot_signature(snapshot)
        if not force and signature == last_rendered_snapshot:
            return
        if show_history:
            print_fn(render_history(entries=list(snapshot.get("history", []))))
        elif show_settings:
            print_fn(
                render_settings(
                    save_transcriptions_to_file=bool(snapshot.get("save_transcriptions_to_file", False))
                )
            )
        else:
            actions = console_available_actions(
                recording_status=str(snapshot.get("recording_status", "idle")),
                session_status=str(snapshot.get("session_status", "idle")),
            )
            print_fn(
                render_console(
                    status_line=status_override or str(snapshot.get("status_line", "Idle")),
                    last_transcription_line=str(snapshot.get("last_transcription_line", "None")),
                    actions=actions,
                )
            )
        last_rendered_snapshot = signature

    def perform_action(action: str) -> bool:
        nonlocal status_override
        status_override = feedback_message(action=action)
        redraw(force=True)
        try:
            execute_action(action)
            status_override = ""
            redraw(force=True)
            return True
        except Exception as exc:
            status_override = f"Error: {exc}"
            redraw(force=True)
            return False

    redraw(force=True)
    while True:
        snapshot = status_snapshot()
        redraw(snapshot)
        if pending_shutdown:
            if str(snapshot.get("recording_status", "idle")) != "transcribing":
                pending_shutdown = False
                if str(snapshot.get("session_status", "idle")) != "idle":
                    if perform_action("end-session"):
                        return
                else:
                    return

        if not key_available_fn():
            sleep_fn(0.1)
            continue

        key = read_key()
        if key == "\x1b":
            if show_history or show_settings:
                show_history = False
                show_settings = False
                status_override = ""
                redraw(force=True)
            continue
        if show_settings and key == "1":
            enabled = toggle_setting("save_transcriptions_to_file")
            status_override = f"Saved transcriptions to file: {'On' if enabled else 'Off'}"
            redraw(force=True)
            continue

        actions = {entry[0]: entry for entry in console_available_actions(
            recording_status=str(snapshot.get("recording_status", "idle")),
            session_status=str(snapshot.get("session_status", "idle")),
        )}
        entry = actions.get(key)
        if key == "h":
            show_history = not show_history
            if show_history:
                show_settings = False
            redraw(force=True)
            continue
        if key == "s":
            show_settings = not show_settings
            if show_settings:
                show_history = False
            redraw(force=True)
            continue
        if entry is None:
            status_override = f"Error: Unknown key: {key}"
            redraw(force=True)
            continue
        if entry[2] == "quit-console":
            recording = str(snapshot.get("recording_status", "idle"))
            session = str(snapshot.get("session_status", "idle"))
            if recording in {"recording", "ambiguous"}:
                if not perform_action("cancel-recording"):
                    continue
                snapshot = status_snapshot()
                recording = str(snapshot.get("recording_status", "idle"))
                session = str(snapshot.get("session_status", "idle"))
            if recording == "transcribing":
                pending_shutdown = True
                status_override = "Waiting to shut down after transcription..."
                redraw(force=True)
                continue
            if session != "idle":
                if perform_action("end-session"):
                    return
                continue
            return
        perform_action(entry[2])
