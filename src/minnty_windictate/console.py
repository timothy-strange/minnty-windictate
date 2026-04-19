from __future__ import annotations

import msvcrt
from typing import Callable


def console_actions(*, recording_active: bool, session_ready: bool) -> list[tuple[str, str]]:
    actions = [("t", "Stop and transcribe" if recording_active else "Start recording")]
    actions.append(("c", "Cancel recording"))
    actions.append(("m", "Start session" if not session_ready else "Stop session"))
    actions.append(("r", "Refresh"))
    actions.append(("q", "Quit"))
    return actions


def render_console(*, status_line: str, last_result_line: str, actions: list[tuple[str, str]]) -> str:
    lines = [
        "\x1b[2J\x1b[HTranscriber",
        f"Status: {status_line}",
        f"Last result: {last_result_line}",
        "",
        "Available actions:",
    ]
    for key, label in actions:
        lines.append(f"  [{key}] {label}")
    return "\n".join(lines)


def read_key() -> str:
    while True:
        key = msvcrt.getwch().lower()
        if key in {"\x00", "\xe0"}:
            _ignored = msvcrt.getwch()
            continue
        return key


def run_console(
    *,
    status_report: Callable[[], str],
    toggle: Callable[[], str],
    cancel: Callable[[], str],
    session_start: Callable[[], str],
    session_stop: Callable[[], str],
    is_recording_active: Callable[[], bool],
    is_session_ready: Callable[[], bool],
    print_fn=print,
) -> None:
    last_result = "None"
    while True:
        actions = console_actions(
            recording_active=is_recording_active(),
            session_ready=is_session_ready(),
        )
        print_fn(
            render_console(
                status_line=status_report(),
                last_result_line=last_result,
                actions=actions,
            )
        )
        key = read_key()
        if key == "q":
            return
        if key == "r":
            continue
        try:
            if key == "t":
                last_result = toggle() or "ok"
            elif key == "c":
                last_result = cancel() or "ok"
            elif key == "m":
                if is_session_ready():
                    last_result = session_stop() or "ok"
                else:
                    last_result = session_start() or "ok"
        except Exception as exc:
            last_result = f"Error: {exc}"
