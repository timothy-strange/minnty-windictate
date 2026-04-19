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
    service.hotkey = "ctrl+alt+r"

    status = service.status()

    assert status["recording"] is False


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
