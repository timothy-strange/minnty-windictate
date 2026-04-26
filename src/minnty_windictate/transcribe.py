from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

from .config import NVIDIA_LIBS_DIR, SessionConfig

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

VAD_PARAMETERS = {
    "min_silence_duration_ms": 900,
    "speech_pad_ms": 300,
}

_NVIDIA_DLL_DIRECTORY_HANDLE = None


def configure_runtime_library_path() -> None:
    global _NVIDIA_DLL_DIRECTORY_HANDLE

    if not NVIDIA_LIBS_DIR.exists():
        return

    libs_path = str(NVIDIA_LIBS_DIR)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if libs_path.lower() not in {part.lower() for part in path_parts if part}:
        os.environ["PATH"] = libs_path + os.pathsep + os.environ.get("PATH", "")

    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None and _NVIDIA_DLL_DIRECTORY_HANDLE is None:
        _NVIDIA_DLL_DIRECTORY_HANDLE = add_dll_directory(libs_path)


def whisper_runtime_version() -> tuple[int, int, int]:
    return sys.version_info.major, sys.version_info.minor, sys.version_info.micro


def ensure_supported_whisper_runtime() -> None:
    version_tuple = whisper_runtime_version()
    if version_tuple >= (3, 14, 0):
        version = ".".join(str(part) for part in version_tuple)
        raise RuntimeError(
            "faster-whisper is not stable on Python "
            f"{version} in this Windows setup. Use Python 3.12 or 3.13 instead."
        )


def build_model(session: SessionConfig) -> "WhisperModel":
    ensure_supported_whisper_runtime()
    configure_runtime_library_path()
    from faster_whisper import WhisperModel

    return WhisperModel(
        session.model_path,
        device=session.device,
        compute_type=session.compute_type,
    )


def transcribe_file(path: str, *, model: Any, session: SessionConfig) -> str:
    segments, _info = model.transcribe(
        str(path),
        beam_size=session.beam_size,
        language=session.language,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters=VAD_PARAMETERS,
    )
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return text
