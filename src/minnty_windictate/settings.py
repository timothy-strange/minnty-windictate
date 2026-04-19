from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .config import SETTINGS_STATE_PATH, cancel_hotkey, ensure_directories, hotkey


@dataclass(frozen=True)
class Settings:
    input_device: str | int | None = None
    sample_rate: int = 16000
    channels: int = 1
    record_seconds: float = 8.0
    auto_paste: bool = True
    hotkey: str = ""
    cancel_hotkey: str = ""


def default_settings() -> Settings:
    return Settings(hotkey=hotkey(), cancel_hotkey=cancel_hotkey())


def _coerce_settings(payload: dict | None) -> Settings:
    defaults = default_settings()
    if not isinstance(payload, dict):
        return defaults

    input_device = payload.get("input_device")
    if not isinstance(input_device, (str, int)):
        input_device = None

    sample_rate = payload.get("sample_rate", defaults.sample_rate)
    channels = payload.get("channels", defaults.channels)
    record_seconds = payload.get("record_seconds", defaults.record_seconds)
    auto_paste = payload.get("auto_paste", defaults.auto_paste)
    saved_hotkey = payload.get("hotkey", defaults.hotkey)
    saved_cancel_hotkey = payload.get("cancel_hotkey", defaults.cancel_hotkey)

    return Settings(
        input_device=input_device,
        sample_rate=sample_rate if isinstance(sample_rate, int) and sample_rate > 0 else defaults.sample_rate,
        channels=channels if isinstance(channels, int) and channels > 0 else defaults.channels,
        record_seconds=(
            record_seconds
            if isinstance(record_seconds, (int, float)) and record_seconds > 0
            else defaults.record_seconds
        ),
        auto_paste=bool(auto_paste),
        hotkey=saved_hotkey if isinstance(saved_hotkey, str) and saved_hotkey else defaults.hotkey,
        cancel_hotkey=(
            saved_cancel_hotkey
            if isinstance(saved_cancel_hotkey, str) and saved_cancel_hotkey
            else defaults.cancel_hotkey
        ),
    )


def read_settings() -> Settings:
    if not SETTINGS_STATE_PATH.exists():
        return default_settings()
    try:
        payload = json.loads(SETTINGS_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_settings()
    return _coerce_settings(payload)


def save_settings(settings: Settings) -> None:
    ensure_directories()
    SETTINGS_STATE_PATH.write_text(
        json.dumps(asdict(settings), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def update_settings(**changes: object) -> Settings:
    current = asdict(read_settings())
    current.update(changes)
    updated = _coerce_settings(current)
    save_settings(updated)
    return updated
