from minnty_windictate.console import console_actions, render_console, run_console


def test_console_actions_change_with_state():
    idle_actions = console_actions(recording_active=False, session_ready=False)
    active_actions = console_actions(recording_active=True, session_ready=True)

    assert ("t", "Start recording") in idle_actions
    assert ("m", "Start session") in idle_actions
    assert ("t", "Stop and transcribe") in active_actions
    assert ("m", "Stop session") in active_actions


def test_render_console_includes_status_and_actions():
    rendered = render_console(
        status_line="recording: idle",
        last_result_line="None",
        actions=[("t", "Start recording"), ("q", "Quit")],
    )

    assert "Transcriber" in rendered
    assert "Status: recording: idle" in rendered
    assert "[t] Start recording" in rendered


def test_run_console_executes_actions(monkeypatch):
    keys = iter(["t", "m", "q"])
    outputs: list[str] = []

    monkeypatch.setattr("minnty_windictate.console.read_key", lambda: next(keys))

    run_console(
        status_report=lambda: "recording: idle\nsession: idle",
        toggle=lambda: "recording started",
        cancel=lambda: "cancelled",
        session_start=lambda: "session ready",
        session_stop=lambda: "session stopped",
        is_recording_active=lambda: False,
        is_session_ready=lambda: False,
        print_fn=outputs.append,
    )

    assert any("Last result: recording started" in output for output in outputs)
