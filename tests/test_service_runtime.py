from minnty_windictate.service_runtime import service_is_running


def test_service_is_running_false_without_state(tmp_path):
    assert service_is_running(tmp_path / "service.json") is False


def test_service_is_running_checks_process(monkeypatch, tmp_path):
    path = tmp_path / "service.json"
    path.write_text(
        '{"pid": 123, "port": 5555, "token": "abc", "hotkey": "ctrl+alt+space", "cancel_hotkey": "ctrl+alt+backspace", "started_at": 1.0}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "minnty_windictate.service_runtime.process_is_running",
        lambda pid: pid == 123,
    )

    assert service_is_running(path) is True


def test_send_service_command_retries_after_connection_failure(monkeypatch):
    from minnty_windictate.service_runtime import ServiceState, send_service_command

    calls = {"count": 0}
    state = ServiceState(
        pid=1,
        port=5555,
        token="abc",
        hotkey="ctrl+alt+space",
        cancel_hotkey="ctrl+alt+backspace",
        started_at=1.0,
    )

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def send(self, payload):
            self.payload = payload

        def recv(self):
            return {"ok": True, "message": "done"}

    def connect(_state):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("stale")
        return FakeConn()

    monkeypatch.setattr(
        "minnty_windictate.service_runtime.ensure_service",
        lambda hotkey, cancel_hotkey, autostart: state,
    )
    monkeypatch.setattr(
        "minnty_windictate.service_runtime.start_service",
        lambda hotkey, cancel_hotkey: state,
    )
    monkeypatch.setattr("minnty_windictate.service_runtime._connect", connect)
    monkeypatch.setattr("minnty_windictate.service_runtime.clear_service_state", lambda path=None: None)

    response = send_service_command(
        "status",
        hotkey="ctrl+alt+space",
        cancel_hotkey="ctrl+alt+backspace",
        autostart=True,
    )

    assert response["message"] == "done"
    assert calls["count"] == 2
