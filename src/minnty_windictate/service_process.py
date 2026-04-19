from __future__ import annotations

import threading
import time
import wave
from multiprocessing.connection import Listener
from pathlib import Path

import keyboard
import sounddevice as sd

from .config import LATEST_WAV_PATH, SessionConfig, resolve_documents_dir, session_config
from .notify import APP_NAME, notify
from .settings import read_settings
from .transcribe import build_model, transcribe_file
from .typing import type_text


class ResidentService:
    def __init__(self, *, hotkey: str, cancel_hotkey: str) -> None:
        self.hotkey = hotkey
        self.cancel_hotkey = cancel_hotkey
        self._model = None
        self._model_config: SessionConfig | None = None
        self._lock = threading.RLock()
        self._recording_thread: threading.Thread | None = None
        self._recording_stop = threading.Event()
        self._recording_ready = threading.Event()
        self._recording_error: Exception | None = None
        self._recording_path: Path | None = None
        self._recording_started_at: float | None = None
        self._recording_status = "idle"
        self._session_status = "idle"
        self._history: list[dict[str, object]] = []
        self._last_transcription_line = "None"
        self._toggle_hotkey_id = keyboard.add_hotkey(self.hotkey, self._handle_hotkey)
        self._cancel_hotkey_id = keyboard.add_hotkey(self.cancel_hotkey, self._handle_cancel_hotkey)


    def _append_history(self, entry: dict[str, object]) -> None:
        payload = {"timestamp": time.strftime("%H:%M:%S"), **entry}
        self._history.append(payload)
        if len(self._history) > 100:
            self._history = self._history[-100:]


    def _persist_transcription(self, text: str) -> None:
        settings = read_settings()
        if not settings.save_transcriptions_to_file or not text:
            return
        documents_dir = resolve_documents_dir() / "transcriber"
        documents_dir.mkdir(parents=True, exist_ok=True)
        file_path = documents_dir / f"transcription-{time.strftime('%Y-%m')}.txt"
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{text}\n\n")


    def _set_last_transcription(self, *, text: str, audio_duration_s: float | None, transcription_duration_s: float | None) -> None:
        parts = [time.strftime("%H:%M:%S"), "ok"]
        word_count = len(text.split()) if text else 0
        if word_count:
            parts.append(f"{word_count} words")
        if audio_duration_s is not None:
            parts.append(f"audio {audio_duration_s:.1f}s")
        if transcription_duration_s is not None:
            parts.append(f"transcribe {transcription_duration_s:.1f}s")
        self._last_transcription_line = " ".join(parts)
        self._append_history(
            {
                "kind": "transcription",
                "action": "transcribe",
                "result": "ok",
                "message": self._last_transcription_line,
                "text": text,
                "word_count": word_count,
                "audio_duration_s": audio_duration_s,
                "transcription_duration_s": transcription_duration_s,
            }
        )


    def _coerce_device(self, value: str | int | None) -> str | int | None:
        if isinstance(value, int) or value is None:
            return value
        if value.isdigit():
            return int(value)
        return value


    def _recording_is_active(self) -> bool:
        return self._recording_thread is not None and self._recording_thread.is_alive()


    def close(self) -> None:
        keyboard.remove_hotkey(self._toggle_hotkey_id)
        keyboard.remove_hotkey(self._cancel_hotkey_id)


    def _handle_hotkey(self) -> None:
        with self._lock:
            try:
                self.toggle()
            except Exception as exc:
                self._append_history(
                    {
                        "kind": "error",
                        "action": "toggle",
                        "result": "error",
                        "message": str(exc),
                    }
                )
                notify(f"{APP_NAME} error", str(exc))


    def _handle_cancel_hotkey(self) -> None:
        with self._lock:
            try:
                if self._recording_thread is not None:
                    self.cancel_recording()
            except Exception as exc:
                self._append_history(
                    {
                        "kind": "error",
                        "action": "cancel-recording",
                        "result": "error",
                        "message": str(exc),
                    }
                )
                notify(f"{APP_NAME} error", str(exc))


    def _ensure_model(self) -> None:
        current = session_config()
        if self._model is not None and self._model_config == current:
            return
        self._session_status = "loading"
        self._model = build_model(current)
        self._model_config = current
        self._session_status = "ready"


    def session_start(self) -> str:
        with self._lock:
            self._ensure_model()
            self._append_history({"kind": "action", "action": "start-session", "result": "ok", "message": "Session ready"})
            notify(APP_NAME, "Transcription session ready")
            return "Session ready"


    def session_stop(self) -> str:
        with self._lock:
            self._model = None
            self._model_config = None
            self._session_status = "idle"
            self._append_history({"kind": "action", "action": "end-session", "result": "ok", "message": "Session stopped"})
            notify(APP_NAME, "Session stopped")
            return "Session stopped"


    def _record_worker(self, *, path: Path, sample_rate: int, channels: int, device: str | int | None) -> None:
        self._recording_error = None
        self._recording_ready.clear()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
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
                    self._recording_ready.set()
                    while not self._recording_stop.is_set():
                        time.sleep(0.1)
        except Exception as exc:
            self._recording_error = exc
        finally:
            self._recording_ready.set()


    def _finish_recording_thread(self, *, raise_error: bool) -> None:
        if self._recording_thread is None:
            raise RuntimeError("No active recording.")
        self._recording_stop.set()
        self._recording_thread.join(timeout=10.0)
        if self._recording_thread.is_alive():
            raise RuntimeError("Recorder thread did not stop in time.")
        self._recording_thread = None
        self._recording_stop = threading.Event()
        self._recording_ready = threading.Event()
        if self._recording_error is not None:
            error = self._recording_error
            self._recording_error = None
            if raise_error:
                raise error


    def _wait_for_recording_start(self, *, timeout: float = 2.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._recording_ready.wait(timeout=0.05):
                if self._recording_error is not None:
                    error = self._recording_error
                    self._recording_thread = None
                    self._recording_stop = threading.Event()
                    self._recording_ready = threading.Event()
                    self._recording_error = None
                    raise error
                if self._recording_is_active():
                    return
            if self._recording_thread is not None and not self._recording_thread.is_alive():
                break
        raise RuntimeError("Recording did not start successfully.")


    def start_recording(self) -> str:
        with self._lock:
            if self._recording_is_active():
                raise RuntimeError("Recording is already active.")
            settings = read_settings()
            self._recording_path = LATEST_WAV_PATH
            self._recording_started_at = time.time()
            self._recording_thread = threading.Thread(
                target=self._record_worker,
                kwargs={
                    "path": self._recording_path,
                    "sample_rate": settings.sample_rate,
                    "channels": settings.channels,
                    "device": self._coerce_device(settings.input_device),
                },
                daemon=True,
            )
            self._recording_thread.start()
            self._wait_for_recording_start()
            self._recording_status = "recording"
            self._append_history({"kind": "action", "action": "start-recording", "result": "ok", "message": "Recording started"})
            notify(APP_NAME, "Recording started")
            return "Recording started"


    def _transcribe_current(self, *, should_type: bool) -> str:
        if self._recording_path is None:
            raise RuntimeError("No recording available.")
        self._ensure_model()
        assert self._model is not None
        assert self._model_config is not None
        text = transcribe_file(str(self._recording_path), model=self._model, session=self._model_config)
        settings = read_settings()
        if should_type and settings.auto_paste:
            type_text(text)
        return text


    def stop_recording(self, *, should_type: bool) -> str:
        with self._lock:
            audio_duration_s = None
            if self._recording_started_at is not None:
                audio_duration_s = max(0.0, time.time() - self._recording_started_at)
            self._recording_status = "transcribing"
            self._finish_recording_thread(raise_error=True)
            transcribe_started_at = time.time()
            text = self._transcribe_current(should_type=should_type)
            transcription_duration_s = max(0.0, time.time() - transcribe_started_at)
            self._persist_transcription(text)
            self._set_last_transcription(
                text=text,
                audio_duration_s=audio_duration_s,
                transcription_duration_s=transcription_duration_s,
            )
            self._recording_status = "idle"
            self._recording_started_at = None
            notify(APP_NAME, "Recording stopped and transcribed")
            return text


    def cancel_recording(self) -> str:
        with self._lock:
            self._finish_recording_thread(raise_error=False)
            if self._recording_path is not None:
                self._recording_path.unlink(missing_ok=True)
                self._recording_path = None
            self._recording_status = "idle"
            self._recording_started_at = None
            self._append_history({"kind": "action", "action": "cancel-recording", "result": "ok", "message": "Recording cancelled"})
            notify(APP_NAME, "Recording cancelled")
            return "Recording cancelled"


    def toggle(self) -> str:
        if self._recording_thread is not None:
            return self.stop_recording(should_type=True)
        return self.start_recording()


    def listen_once(self, *, seconds: float | None, device: str | None, sample_rate: int | None, should_type: bool) -> str:
        with self._lock:
            settings = read_settings()
            selected_seconds = seconds if seconds is not None else settings.record_seconds
            if selected_seconds <= 0:
                raise RuntimeError("Recording duration must be greater than zero.")
            selected_device = self._coerce_device(settings.input_device if device is None else device)
            selected_sample_rate = sample_rate if sample_rate is not None else settings.sample_rate
            frames = int(selected_seconds * selected_sample_rate)
            if frames <= 0:
                raise RuntimeError("Recording duration must be greater than zero.")
            audio = sd.rec(
                frames,
                samplerate=selected_sample_rate,
                channels=settings.channels,
                dtype="int16",
                device=selected_device,
            )
            sd.wait()
            path = LATEST_WAV_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(settings.channels)
                handle.setsampwidth(2)
                handle.setframerate(selected_sample_rate)
                handle.writeframes(audio.tobytes())
            self._recording_path = path
            text = self._transcribe_current(should_type=should_type)
            notify(APP_NAME, "Transcription complete")
            return text


    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "recording": self._recording_is_active(),
                "session": self._model is not None,
                "recording_status": self._recording_status,
                "session_status": self._session_status,
                "latest_wav": str(LATEST_WAV_PATH),
                "hotkey": self.hotkey,
                "cancel_hotkey": self.cancel_hotkey,
                "last_transcription_line": self._last_transcription_line,
                "history": list(self._history),
            }


def serve(*, port: int, token: str, hotkey: str, cancel_hotkey: str) -> None:
    service = ResidentService(hotkey=hotkey, cancel_hotkey=cancel_hotkey)
    listener = Listener(("127.0.0.1", port), authkey=token.encode("utf-8"))
    try:
        running = True
        while running:
            with listener.accept() as conn:
                request = conn.recv()
                action = request.get("action") if isinstance(request, dict) else None
                try:
                    if action == "ping":
                        conn.send({"ok": True, "status": "ready"})
                    elif action == "status":
                        conn.send({"ok": True, **service.status()})
                    elif action == "toggle":
                        conn.send({"ok": True, "message": service.toggle()})
                    elif action == "cancel":
                        conn.send({"ok": True, "message": service.cancel_recording()})
                    elif action == "session-start":
                        conn.send({"ok": True, "message": service.session_start()})
                    elif action == "session-stop":
                        conn.send({"ok": True, "message": service.session_stop()})
                    elif action == "listen-once":
                        conn.send({
                            "ok": True,
                            "text": service.listen_once(
                                seconds=request.get("seconds"),
                                device=request.get("device"),
                                sample_rate=request.get("sample_rate"),
                                should_type=bool(request.get("should_type", False)),
                            ),
                        })
                    elif action == "shutdown":
                        message = "Resident service stopped"
                        if service._recording_thread is not None:
                            try:
                                service.cancel_recording()
                            except Exception:
                                pass
                        try:
                            service.session_stop()
                        except Exception:
                            pass
                        conn.send({"ok": True, "message": message})
                        running = False
                    else:
                        conn.send({"ok": False, "error": "Unknown action"})
                except Exception as exc:
                    conn.send({"ok": False, "error": str(exc)})
    finally:
        listener.close()
        service.close()
