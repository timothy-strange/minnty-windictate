from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


def list_input_devices() -> list[dict[str, object]]:
    devices: list[dict[str, object]] = []
    default_input, _default_output = sd.default.device
    for index, entry in enumerate(sd.query_devices()):
        max_input = int(entry.get("max_input_channels", 0))
        if max_input <= 0:
            continue
        devices.append(
            {
                "index": index,
                "name": str(entry.get("name", f"Input {index}")),
                "channels": max_input,
                "default_samplerate": int(entry.get("default_samplerate", 16000)),
                "is_default": index == default_input,
            }
        )
    return devices


def format_input_devices(devices: list[dict[str, object]]) -> str:
    if not devices:
        return "No input devices found."
    lines: list[str] = []
    for device in devices:
        label = " (default)" if device["is_default"] else ""
        lines.append(
            f"[{device['index']}] {device['name']} - {device['channels']}ch @ {device['default_samplerate']}Hz{label}"
        )
    return "\n".join(lines)


def record_wav(
    *,
    path: Path,
    seconds: float,
    sample_rate: int,
    channels: int,
    device: str | int | None,
) -> Path:
    frames = int(seconds * sample_rate)
    if frames <= 0:
        raise RuntimeError("Recording duration must be greater than zero.")

    audio = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        device=device,
    )
    sd.wait()

    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.asarray(audio, dtype=np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return path
