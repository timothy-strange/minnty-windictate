from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass

from .config import resolve_model_path


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
            "python_runtime",
            sys.version_info < (3, 14),
            f"use Python 3.12 or 3.13 for faster-whisper stability; current {platform.python_version()}",
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
        CheckResult(
            "model_path",
            resolve_model_path().exists(),
            f"expected local model at {resolve_model_path()}",
        ),
    ]
    return checks


def format_checks(checks: list[CheckResult]) -> str:
    lines: list[str] = []
    for check in checks:
        state = "ok" if check.ok else "missing"
        lines.append(f"{check.name}: {state} ({check.detail})")
    return "\n".join(lines)
