from dataclasses import dataclass
from types import SimpleNamespace

import minnty_windictate.app as app


@dataclass(frozen=True)
class FakeSessionConfig:
    model_path: str
    device: str
    compute_type: str
    beam_size: int
    language: str | None


@dataclass(frozen=True)
class FakeSettings:
    hotkey: str
    cancel_hotkey: str = "ctrl+alt+backspace"
    save_transcriptions_to_file: bool = False


def test_config_report_includes_paths(monkeypatch):
    monkeypatch.setattr(app, "read_settings", lambda: FakeSettings(hotkey="ctrl+alt+r"))
    monkeypatch.setattr(
        app,
        "session_config",
        lambda: FakeSessionConfig(
            model_path="C:/Users/danhu/Documents/whisper/faster-whisper-large-v3",
            device="auto",
            compute_type="auto",
            beam_size=5,
            language=None,
        ),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: False)

    report = app._config_report()

    assert "config_dir:" in report
    assert "session:" in report
    assert "settings:" in report


def test_status_report_shows_unavailable_when_service_is_down(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: False)

    report = app._status_report()

    assert "resident: stopped" in report
    assert "recording: unavailable" in report
    assert "session: unavailable" in report
    assert "hotkey: ctrl+shift+d" in report
    assert "cancel_hotkey: ctrl+shift+backspace" in report


def test_status_report_reads_service_state(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: True)
    monkeypatch.setattr(
        app,
        "_service_status",
        lambda autostart: {
            "recording": True,
            "session": True,
            "recording_status": "recording",
            "session_status": "ready",
            "latest_wav": "C:/tmp/latest.wav",
            "hotkey": "ctrl+shift+d",
            "cancel_hotkey": "ctrl+shift+backspace",
        },
    )

    report = app._status_report()

    assert "resident: running" in report
    assert "recording: recording" in report
    assert "session: ready" in report
    assert "cancel_hotkey: ctrl+shift+backspace" in report


def test_status_report_falls_back_to_idle_when_ipc_is_broken(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: True)
    monkeypatch.setattr(app, "_service_status", lambda autostart: (_ for _ in ()).throw(RuntimeError("stale")))

    report = app._status_report()

    assert "resident: stopped" in report


def test_toggle_uses_resident_service(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(
        app,
        "send_service_command",
        lambda action, **kwargs: {"ok": True, "message": "Recording started"},
    )

    assert app._toggle() == "Recording started"


def test_toggle_does_not_autostart_service(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    captured = {}
    monkeypatch.setattr(
        app,
        "send_service_command",
        lambda action, **kwargs: captured.update(kwargs) or {"ok": True, "message": "Recording started"},
    )

    app._toggle()

    assert captured["autostart"] is False


def test_cancel_uses_resident_service(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(
        app,
        "send_service_command",
        lambda action, **kwargs: {"ok": True, "message": "Recording cancelled"},
    )

    assert app._cancel() == "Recording cancelled"


def test_start_and_stop_session_use_resident_service(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(
        app,
        "send_service_command",
        lambda action, **kwargs: {"ok": True, "message": f"{action} ok"},
    )

    assert app._start_session() == "session-start ok"
    assert app._stop_session() == "session-stop ok"


def test_console_status_snapshot_uses_service_history(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(
            hotkey="ctrl+shift+d",
            cancel_hotkey="ctrl+shift+backspace",
            save_transcriptions_to_file=True,
        ),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: True)
    monkeypatch.setattr(
        app,
        "_service_status",
        lambda autostart: {
            "recording_status": "transcribing",
            "session_status": "ready",
            "last_transcription_line": "12:00:00 ok 4 words",
            "history": [{"action": "transcribe", "result": "ok"}],
        },
    )

    snapshot = app._console_status_snapshot()

    assert snapshot["status_line"] == "Transcribing..."
    assert snapshot["last_transcription_line"] == "12:00:00 ok 4 words"
    assert snapshot["save_transcriptions_to_file"] is True


def test_toggle_setting_flips_save_transcriptions(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(save_transcriptions_to_file=False),
    )
    monkeypatch.setattr(
        app,
        "update_settings",
        lambda **changes: SimpleNamespace(save_transcriptions_to_file=changes["save_transcriptions_to_file"]),
    )

    assert app._toggle_setting("save_transcriptions_to_file") is True


def test_config_hotkey_change_restarts_running_service(monkeypatch):
    class Args:
        command = "config"
        input_device = None
        sample_rate = None
        channels = None
        record_seconds = None
        hotkey = "ctrl+shift+d"
        cancel_hotkey = "ctrl+shift+backspace"
        auto_paste = None

    class Parser:
        @staticmethod
        def parse_args():
            return Args()

    restarted = {}
    monkeypatch.setattr(app, "build_parser", lambda: Parser())
    monkeypatch.setattr(
        app,
        "update_settings",
        lambda **changes: SimpleNamespace(
            hotkey=changes["hotkey"],
            cancel_hotkey=changes["cancel_hotkey"],
        ),
    )
    monkeypatch.setattr(app, "service_is_running", lambda: True)
    monkeypatch.setattr(
        app,
        "start_service",
        lambda hotkey, cancel_hotkey: restarted.update({"hotkey": hotkey, "cancel_hotkey": cancel_hotkey}) or SimpleNamespace(port=1),
    )
    monkeypatch.setattr(app, "_config_report", lambda: "config")

    app.main()

    assert restarted["hotkey"] == "ctrl+shift+d"
    assert restarted["cancel_hotkey"] == "ctrl+shift+backspace"


def test_cleanup_stops_service_and_removes_files(monkeypatch, tmp_path):
    latest = tmp_path / "latest.wav"
    session = tmp_path / "session.json"
    latest.write_text("x", encoding="utf-8")
    session.write_text("x", encoding="utf-8")
    monkeypatch.setattr(app, "LATEST_WAV_PATH", latest)
    monkeypatch.setattr(app, "SESSION_STATE_PATH", session)
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app, "stop_service", lambda hotkey, cancel_hotkey: "Resident service stopped")

    report = app._cleanup()

    assert "Removed:" in report
    assert not latest.exists()
    assert not session.exists()


def test_main_without_command_runs_console(monkeypatch):
    class Args:
        command = None

    class Parser:
        @staticmethod
        def parse_args():
            return Args()

    parser = Parser()
    called = {"run": False}

    monkeypatch.setattr(app, "build_parser", lambda: parser)
    monkeypatch.setattr(app, "_run_console", lambda: called.__setitem__("run", True))

    app.main()

    assert called["run"] is True


def test_run_console_starts_and_stops_service(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(app, "_run_hotkeys", lambda: calls.append("start"))
    monkeypatch.setattr(app, "run_console", lambda **kwargs: calls.append("console"))
    monkeypatch.setattr(app, "_stop_hotkeys", lambda: calls.append("stop") or "stopped")
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app.keyboard, "add_hotkey", lambda hotkey, callback: hotkey)
    monkeypatch.setattr(app.keyboard, "remove_hotkey", lambda hotkey_id: calls.append(f"remove:{hotkey_id}"))

    app._run_console()

    assert calls == [
        "start",
        "console",
        "remove:ctrl+shift+d",
        "remove:ctrl+shift+backspace",
        "stop",
    ]


def test_run_console_stops_service_on_console_error(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(app, "_run_hotkeys", lambda: calls.append("start"))
    monkeypatch.setattr(app, "run_console", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(app, "_stop_hotkeys", lambda: calls.append("stop") or "stopped")
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app.keyboard, "add_hotkey", lambda hotkey, callback: hotkey)
    monkeypatch.setattr(app.keyboard, "remove_hotkey", lambda hotkey_id: calls.append(f"remove:{hotkey_id}"))

    try:
        app._run_console()
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Expected console error to propagate")

    assert calls == [
        "start",
        "remove:ctrl+shift+d",
        "remove:ctrl+shift+backspace",
        "stop",
    ]


def test_run_console_ignores_service_stop_error_on_exit(monkeypatch):
    monkeypatch.setattr(app, "_run_hotkeys", lambda: None)
    monkeypatch.setattr(app, "run_console", lambda **kwargs: None)
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app.keyboard, "add_hotkey", lambda hotkey, callback: hotkey)
    monkeypatch.setattr(app.keyboard, "remove_hotkey", lambda hotkey_id: None)
    monkeypatch.setattr(app, "_stop_hotkeys", lambda: (_ for _ in ()).throw(RuntimeError("shutdown failed")))

    app._run_console()


def test_run_hotkeys_uses_saved_hotkey(monkeypatch):
    started = {}
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(
        app,
        "start_service",
        lambda hotkey, cancel_hotkey: started.update({"hotkey": hotkey, "cancel_hotkey": cancel_hotkey}) or SimpleNamespace(port=12345),
    )

    app._run_hotkeys()

    assert started["hotkey"] == "ctrl+shift+d"
    assert started["cancel_hotkey"] == "ctrl+shift+backspace"


def test_stop_hotkeys_uses_saved_hotkey(monkeypatch):
    monkeypatch.setattr(
        app,
        "read_settings",
        lambda: SimpleNamespace(hotkey="ctrl+shift+d", cancel_hotkey="ctrl+shift+backspace"),
    )
    monkeypatch.setattr(app, "stop_service", lambda hotkey, cancel_hotkey: f"stopped {hotkey} {cancel_hotkey}")

    assert app._stop_hotkeys() == "stopped ctrl+shift+d ctrl+shift+backspace"
