from __future__ import annotations

import importlib.util
import platform
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def environment_checks() -> list[CheckResult]:
    checks = [
        CheckResult("Windows", is_windows(), "required for the port"),
        CheckResult(
            "ffmpeg", shutil.which("ffmpeg") is not None, "used for microphone capture"
        ),
        CheckResult(
            "faster_whisper",
            _module_available("faster_whisper"),
            "transcription backend",
        ),
        CheckResult("keyboard", _module_available("keyboard"), "global hotkeys"),
        CheckResult(
            "sounddevice", _module_available("sounddevice"), "audio input capture"
        ),
    ]
    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines: list[str] = []
    for check in checks:
        state = "ok" if check.ok else "missing"
        lines.append(f"{check.name}: {state} ({check.detail})")
    return "\n".join(lines)
