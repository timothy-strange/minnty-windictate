from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecordingState:
    pid: int
    path: str
    stop_path: str
    started_at: float


def read_recording_state(path: Path) -> RecordingState | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    pid = payload.get("pid")
    wav_path = payload.get("path")
    stop_path = payload.get("stop_path")
    started_at = payload.get("started_at")
    if not isinstance(pid, int):
        return None
    if not isinstance(wav_path, str) or not isinstance(stop_path, str):
        return None
    if not isinstance(started_at, (int, float)):
        started_at = time.time()
    return RecordingState(
        pid=pid,
        path=wav_path,
        stop_path=stop_path,
        started_at=float(started_at),
    )


def write_recording_state(path: Path, state: RecordingState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True), encoding="utf-8")


def clear_recording_state(path: Path) -> None:
    path.unlink(missing_ok=True)


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
