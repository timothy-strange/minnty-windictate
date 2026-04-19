from minnty_windictate.session_runtime import SessionState, session_is_running


def test_session_is_running_false_without_state(tmp_path):
    assert session_is_running(tmp_path / "session.json") is False


def test_session_is_running_checks_process(monkeypatch, tmp_path):
    path = tmp_path / "session.json"
    path.write_text(
        '{"pid": 123, "port": 5555, "token": "abc", "started_at": 1.0}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "minnty_windictate.session_runtime.process_is_running",
        lambda pid: pid == 123,
    )

    assert session_is_running(path) is True


def test_transcribe_via_session_uses_existing_server(monkeypatch, tmp_path):
    from minnty_windictate.config import SessionConfig
    from minnty_windictate.session_runtime import transcribe_via_session

    session = SessionConfig(
        model_name="large-v3",
        device="cpu",
        compute_type="int8",
        beam_size=5,
        language=None,
    )
    state = SessionState(pid=1, port=1234, token="token", started_at=1.0)
    messages: list[dict[str, object]] = []

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def send(self, payload):
            messages.append(payload)

        def recv(self):
            return {"ok": True, "text": "hello"}

    monkeypatch.setattr(
        "minnty_windictate.session_runtime.ensure_session_server",
        lambda _session: state,
    )
    monkeypatch.setattr(
        "minnty_windictate.session_runtime.connect_to_session",
        lambda _state: FakeConn(),
    )

    result = transcribe_via_session(tmp_path / "audio.wav", session)

    assert result == "hello"
    assert messages == [{"action": "transcribe", "path": str(tmp_path / "audio.wav")}]
