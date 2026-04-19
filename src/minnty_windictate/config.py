from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import cache_dir, config_dir, data_dir

CONFIG_DIR = config_dir()
CACHE_DIR = cache_dir()
DATA_DIR = data_dir()
RECORD_DIR = DATA_DIR / "recordings"
RUNTIME_DIR = CACHE_DIR / "runtime"

RECORDING_STATE_PATH = CACHE_DIR / "recording.json"
SESSION_STATE_PATH = CACHE_DIR / "session.json"
CONSOLE_STATE_PATH = CACHE_DIR / "console.json"
SETTINGS_STATE_PATH = CONFIG_DIR / "settings.json"

LATEST_WAV_PATH = RECORD_DIR / "minnty-windictate-latest.wav"

DEFAULT_MODEL_NAME = "large-v3"
DEFAULT_DEVICE = "auto"
DEFAULT_COMPUTE_TYPE = "auto"
DEFAULT_BEAM_SIZE = 5
DEFAULT_LANGUAGE = None
DEFAULT_HOTKEY = "ctrl+alt+r"
AUTO_PASTE = True


@dataclass(frozen=True)
class SessionConfig:
    model_name: str
    device: str
    compute_type: str
    beam_size: int
    language: str | None


def ensure_directories() -> None:
    for directory in (CONFIG_DIR, CACHE_DIR, DATA_DIR, RECORD_DIR, RUNTIME_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def model_name() -> str:
    return os.environ.get("MINNTY_WINDICTATE_MODEL", DEFAULT_MODEL_NAME)


def hotkey() -> str:
    return os.environ.get("MINNTY_WINDICTATE_HOTKEY", DEFAULT_HOTKEY)


def session_config() -> SessionConfig:
    raw_beam_size = os.environ.get(
        "MINNTY_WINDICTATE_BEAM_SIZE",
        str(DEFAULT_BEAM_SIZE),
    )
    try:
        beam_size = int(raw_beam_size)
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid MINNTY_WINDICTATE_BEAM_SIZE: {raw_beam_size!r} is not an integer"
        ) from exc
    if beam_size <= 0:
        raise RuntimeError(
            f"Invalid MINNTY_WINDICTATE_BEAM_SIZE: {raw_beam_size!r} must be > 0"
        )

    return SessionConfig(
        model_name=model_name(),
        device=os.environ.get("MINNTY_WINDICTATE_DEVICE", DEFAULT_DEVICE),
        compute_type=os.environ.get(
            "MINNTY_WINDICTATE_COMPUTE_TYPE",
            DEFAULT_COMPUTE_TYPE,
        ),
        beam_size=beam_size,
        language=os.environ.get("MINNTY_WINDICTATE_LANGUAGE", DEFAULT_LANGUAGE),
    )


def resolve_documents_dir() -> Path:
    home = Path.home()
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        candidate = Path(one_drive) / "Documents"
        if candidate.exists():
            return candidate
    return home / "Documents"
