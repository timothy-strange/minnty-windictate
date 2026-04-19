from __future__ import annotations

from faster_whisper import WhisperModel

from .config import SessionConfig

VAD_PARAMETERS = {
    "min_silence_duration_ms": 900,
    "speech_pad_ms": 300,
}


def build_model(session: SessionConfig) -> WhisperModel:
    return WhisperModel(
        session.model_name,
        device=session.device,
        compute_type=session.compute_type,
    )


def transcribe_file(path: str, *, model: WhisperModel, session: SessionConfig) -> str:
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
