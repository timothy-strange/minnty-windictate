from minnty_windictate.service_runtime import service_is_running


def test_service_is_running_false_without_state(tmp_path):
    assert service_is_running(tmp_path / "service.json") is False


def test_service_is_running_checks_process(monkeypatch, tmp_path):
    path = tmp_path / "service.json"
    path.write_text(
        '{"pid": 123, "port": 5555, "token": "abc", "hotkey": "ctrl+alt+r", "started_at": 1.0}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "minnty_windictate.service_runtime.process_is_running",
        lambda pid: pid == 123,
    )

    assert service_is_running(path) is True
