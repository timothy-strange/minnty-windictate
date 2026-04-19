from __future__ import annotations

import threading
import time
import wave
from multiprocessing.connection import Listener
from pathlib import Path

import keyboard
import sounddevice as sd

from .config import LATEST_WAV_PATH, SessionConfig, session_config
from .notify import APP_NAME, notify
from .settings import read_settings
from .transcribe import build_model, transcribe_file
from .typing import type_text


class ResidentService:
    def __init__(self, *, hotkey: str) -> None:
        self.hotkey = hotkey
        self._model = None
        self._model_config: SessionConfig | None = None
        self._lock = threading.RLock()
        self._recording_thread: threading.Thread | None = None
        self._recording_stop = threading.Event()
        self._recording_error: Exception | None = None
        self._recording_path: Path | None = None
        self._hotkey_id = keyboard.add_hotkey(self.hotkey, self._handle_hotkey)


    def close(self) -> None:
        keyboard.remove_hotkey(self._hotkey_id)


    def _handle_hotkey(self) -> None:
        with self._lock:
            try:
                self.toggle()
            except Exception as exc:
                notify(f"{APP_NAME} error", str(exc))


    def _ensure_model(self) -> None:
        current = session_config()
        if self._model is not None and self._model_config == current:
            return
        self._model = build_model(current)
        self._model_config = current


    def session_start(self) -> str:
        with self._lock:
            self._ensure_model()
            notify(APP_NAME, "Transcription session ready")
            return "Session ready"


    def session_stop(self) -> str:
        with self._lock:
            self._model = None
            self._model_config = None
            notify(APP_NAME, "Session stopped")
            return "Session stopped"


    def _record_worker(self, *, path: Path, sample_rate: int, channels: int, device: str | int | None) -> None:
        self._recording_error = None
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
                    while not self._recording_stop.is_set():
                        time.sleep(0.1)
        except Exception as exc:
            self._recording_error = exc


    def _finish_recording_thread(self) -> None:
        if self._recording_thread is None:
            raise RuntimeError("No active recording.")
        self._recording_stop.set()
        self._recording_thread.join(timeout=10.0)
        if self._recording_thread.is_alive():
            raise RuntimeError("Recorder thread did not stop in time.")
        self._recording_thread = None
        self._recording_stop = threading.Event()
        if self._recording_error is not None:
            error = self._recording_error
            self._recording_error = None
            raise error


    def start_recording(self) -> str:
        with self._lock:
            if self._recording_thread is not None:
                raise RuntimeError("Recording is already active.")
            settings = read_settings()
            self._recording_path = LATEST_WAV_PATH
            self._recording_thread = threading.Thread(
                target=self._record_worker,
                kwargs={
                    "path": self._recording_path,
                    "sample_rate": settings.sample_rate,
                    "channels": settings.channels,
                    "device": settings.input_device,
                },
                daemon=True,
            )
            self._recording_thread.start()
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
            self._finish_recording_thread()
            text = self._transcribe_current(should_type=should_type)
            notify(APP_NAME, "Recording stopped and transcribed")
            return text


    def cancel_recording(self) -> str:
        with self._lock:
            self._finish_recording_thread()
            if self._recording_path is not None:
                self._recording_path.unlink(missing_ok=True)
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
            selected_device = settings.input_device if device is None else int(device) if device.isdigit() else device
            selected_sample_rate = sample_rate if sample_rate is not None else settings.sample_rate
            frames = int(selected_seconds * selected_sample_rate)
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
                "recording": self._recording_thread is not None,
                "session": self._model is not None,
                "latest_wav": str(LATEST_WAV_PATH),
                "hotkey": self.hotkey,
            }


def serve(*, port: int, token: str, hotkey: str) -> None:
    service = ResidentService(hotkey=hotkey)
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
                        if service._recording_thread is not None:
                            service.cancel_recording()
                        conn.send({"ok": True, "message": service.session_stop()})
                        running = False
                    else:
                        conn.send({"ok": False, "error": "Unknown action"})
                except Exception as exc:
                    conn.send({"ok": False, "error": str(exc)})
    finally:
        listener.close()
        service.close()
