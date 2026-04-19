from contextlib import nullcontext
from types import SimpleNamespace

from minnty_windictate.service_process import ResidentService


def test_coerce_device_turns_numeric_string_into_int():
    service = ResidentService.__new__(ResidentService)

    assert service._coerce_device("3") == 3
    assert service._coerce_device("Mic") == "Mic"


def test_status_reports_dead_recording_thread_as_idle():
    service = ResidentService.__new__(ResidentService)
    service._lock = nullcontext()
    service._recording_thread = SimpleNamespace(is_alive=lambda: False)
    service._model = None
    service.hotkey = "ctrl+alt+space"
    service.cancel_hotkey = "ctrl+alt+backspace"

    status = service.status()

    assert status["recording"] is False
    assert status["cancel_hotkey"] == "ctrl+alt+backspace"


def test_listen_once_rejects_non_positive_duration(monkeypatch):
    service = ResidentService.__new__(ResidentService)
    service._lock = nullcontext()
    monkeypatch.setattr(
        "minnty_windictate.service_process.read_settings",
        lambda: SimpleNamespace(record_seconds=8.0, input_device=None, sample_rate=16000, channels=1),
    )

    try:
        service.listen_once(seconds=0, device=None, sample_rate=None, should_type=False)
    except RuntimeError as exc:
        assert "greater than zero" in str(exc)
    else:
        raise AssertionError("Expected zero-second recording to be rejected")


def test_cancel_recording_discards_recorder_error(monkeypatch, tmp_path):
    service = ResidentService.__new__(ResidentService)
    service._lock = nullcontext()
    service._recording_thread = SimpleNamespace(is_alive=lambda: False, join=lambda timeout: None)
    service._recording_stop = SimpleNamespace(set=lambda: None)
    service._recording_ready = object()
    service._recording_error = RuntimeError("device failed")
    service._recording_path = tmp_path / "audio.wav"
    service._recording_path.write_text("x", encoding="utf-8")

    result = service.cancel_recording()

    assert result == "Recording cancelled"
    assert not service._recording_path


def test_start_recording_fails_if_recorder_dies_during_startup(monkeypatch):
    service = ResidentService.__new__(ResidentService)
    service._lock = nullcontext()
    service._recording_thread = None
    service._recording_stop = SimpleNamespace(set=lambda: None)
    service._recording_ready = SimpleNamespace(wait=lambda timeout: True)
    service._recording_error = RuntimeError("mic busy")
    service._recording_path = None
    monkeypatch.setattr("minnty_windictate.service_process.read_settings", lambda: SimpleNamespace(sample_rate=16000, channels=1, input_device=None))
    monkeypatch.setattr("minnty_windictate.service_process.threading.Thread", lambda **kwargs: SimpleNamespace(start=lambda: None, is_alive=lambda: False))

    try:
        service.start_recording()
    except RuntimeError as exc:
        assert str(exc) == "mic busy"
    else:
        raise AssertionError("Expected recorder startup failure to propagate")
