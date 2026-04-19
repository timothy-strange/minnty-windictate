from dataclasses import dataclass
from types import SimpleNamespace

import minnty_windictate.app as app


@dataclass(frozen=True)
class FakeSessionConfig:
    model_name: str
    device: str
    compute_type: str
    beam_size: int
    language: str | None


@dataclass(frozen=True)
class FakeSettings:
    hotkey: str


def test_config_report_includes_paths(monkeypatch):
    monkeypatch.setattr(app, "read_settings", lambda: FakeSettings(hotkey="ctrl+alt+r"))
    monkeypatch.setattr(
        app,
        "session_config",
        lambda: FakeSessionConfig(
            model_name="large-v3",
            device="auto",
            compute_type="auto",
            beam_size=5,
            language=None,
        ),
    )

    report = app._config_report()

    assert "config_dir:" in report
    assert "session:" in report
    assert "settings:" in report


def test_listen_once_uses_record_transcribe_and_type(monkeypatch, tmp_path):
    calls = {"typed": None}
    monkeypatch.setattr(app, "ensure_directories", lambda: None)
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(
            record_seconds=8.0,
            input_device=None,
            sample_rate=16000,
            channels=1,
            auto_paste=True,
        ),
    )
    monkeypatch.setattr(
        app,
        "record_wav",
        lambda **kwargs: tmp_path / "sample.wav",
    )
    monkeypatch.setattr(
        app,
        "session_config",
        lambda: SimpleNamespace(
            model_name="large-v3",
            device="auto",
            compute_type="auto",
            beam_size=5,
            language=None,
        ),
    )
    monkeypatch.setattr(app, "transcribe_via_session", lambda path, session: "hello world")
    monkeypatch.setattr(app, "type_text", lambda text: calls.__setitem__("typed", text))

    result = app._listen_once(
        seconds=None,
        device=None,
        sample_rate=None,
        should_type=True,
    )

    assert result == "hello world"
    assert calls["typed"] == "hello world"


def test_cleanup_removes_runtime_files(monkeypatch, tmp_path):
    latest = tmp_path / "latest.wav"
    recording = tmp_path / "recording.json"
    session = tmp_path / "session.json"
    latest.write_text("x", encoding="utf-8")
    recording.write_text("x", encoding="utf-8")
    session.write_text("x", encoding="utf-8")
    monkeypatch.setattr(app, "LATEST_WAV_PATH", latest)
    monkeypatch.setattr(app, "RECORDING_STATE_PATH", recording)
    monkeypatch.setattr(app, "SESSION_STATE_PATH", session)

    report = app._cleanup()

    assert "Removed:" in report
    assert not latest.exists()
    assert not recording.exists()
    assert not session.exists()


def test_toggle_starts_when_idle(monkeypatch):
    monkeypatch.setattr(app, "read_recording_state", lambda _path: None)
    monkeypatch.setattr(app, "_start_background_recording", lambda: "Recording started")

    result = app._toggle()

    assert result == "Recording started"


def test_toggle_stops_when_active(monkeypatch):
    state = app.RecordingState(pid=123, path="x.wav", stop_path="x.stop", started_at=1.0)
    monkeypatch.setattr(app, "read_recording_state", lambda _path: state)
    monkeypatch.setattr(app, "process_is_running", lambda _pid: True)
    monkeypatch.setattr(app, "_finish_recording", lambda should_type: "hello world")

    result = app._toggle()

    assert result == "hello world"


def test_cancel_clears_state_and_audio(monkeypatch, tmp_path):
    audio_path = tmp_path / "audio.wav"
    stop_path = tmp_path / "stop.flag"
    audio_path.write_text("x", encoding="utf-8")
    state = app.RecordingState(
        pid=123,
        path=str(audio_path),
        stop_path=str(stop_path),
        started_at=1.0,
    )
    cleared = {"called": False}
    monkeypatch.setattr(app, "read_recording_state", lambda _path: state)
    monkeypatch.setattr(app, "process_is_running", lambda _pid: False)
    monkeypatch.setattr(app, "clear_recording_state", lambda _path: cleared.__setitem__("called", True))

    result = app._cancel()

    assert result == "Recording cancelled"
    assert cleared["called"] is True
    assert not audio_path.exists()


def test_record_background_coerces_numeric_device(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        app,
        "record_until_stopped",
        lambda **kwargs: captured.update(kwargs),
    )

    app._record_background(
        output=str(tmp_path / "audio.wav"),
        stop_path=str(tmp_path / "stop.flag"),
        sample_rate=16000,
        channels=1,
        device="3",
    )

    assert captured["device"] == 3


def test_listen_once_uses_session_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "ensure_directories", lambda: None)
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(
            record_seconds=8.0,
            input_device=None,
            sample_rate=16000,
            channels=1,
            auto_paste=False,
        ),
    )
    monkeypatch.setattr(app, "record_wav", lambda **kwargs: tmp_path / "sample.wav")
    monkeypatch.setattr(
        app,
        "transcribe_via_session",
        lambda path, session: "hello from session",
    )
    monkeypatch.setattr(
        app,
        "session_config",
        lambda: SimpleNamespace(
            model_name="large-v3",
            device="auto",
            compute_type="auto",
            beam_size=5,
            language=None,
        ),
    )

    result = app._listen_once(
        seconds=None,
        device=None,
        sample_rate=None,
        should_type=False,
    )

    assert result == "hello from session"
