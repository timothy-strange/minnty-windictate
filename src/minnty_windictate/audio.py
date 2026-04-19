from __future__ import annotations

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
