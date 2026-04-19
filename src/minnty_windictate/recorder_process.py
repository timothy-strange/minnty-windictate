from __future__ import annotations

import time
import wave
from pathlib import Path

import sounddevice as sd


def record_until_stopped(
    *,
    path: Path,
    stop_path: Path,
    sample_rate: int,
    channels: int,
    device: str | int | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.unlink(missing_ok=True)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)

        def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
            del frames, time_info
            if status:
                raise RuntimeError(str(status))
            handle.writeframes(indata.copy().tobytes())

        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="int16",
            device=device,
            callback=callback,
        ):
            while not stop_path.exists():
                time.sleep(0.1)
