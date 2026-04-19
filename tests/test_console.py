from minnty_windictate.console import console_available_actions, render_console, run_console


def test_console_actions_match_linux_style_states():
    idle_actions = console_available_actions(recording_status="idle", session_status="idle")
    recording_actions = console_available_actions(recording_status="recording", session_status="ready")

    assert ("m", "Start session and load model", "start-session") in idle_actions
    assert ("q", "Quit and unload", "quit-console") in idle_actions
    assert ("h", "History", "history") in idle_actions
    assert ("s", "Settings", "settings") in idle_actions
    assert ("c", "Cancel recording", "cancel-recording") in recording_actions


def test_render_console_includes_last_transcription_and_actions():
    rendered = render_console(
        status_line="Idle",
        last_transcription_line="None",
        actions=[("m", "Start session and load model", "start-session"), ("q", "Quit and unload", "quit-console")],
    )

    assert "Transcriber" in rendered
    assert "Status: Idle" in rendered
    assert "Last transcription: None" in rendered
    assert "[m] Start session and load model" in rendered


def test_run_console_handles_linux_style_keys(monkeypatch):
    keys = iter(["m", "h", "h", "s", "1", "s", "q"])
    outputs: list[str] = []
    actions: list[str] = []

    snapshot = {
        "recording_status": "idle",
        "session_status": "idle",
        "status_line": "Idle",
        "last_transcription_line": "None",
        "history": [],
        "save_transcriptions_to_file": False,
    }

    monkeypatch.setattr("minnty_windictate.console.read_key", lambda: next(keys))

    def execute_action(action: str) -> str:
        actions.append(action)
        if action == "start-session":
            snapshot["session_status"] = "ready"
            return "Session ready"
        if action == "end-session":
            snapshot["session_status"] = "idle"
            return "Session stopped"
        return "ok"

    run_console(
        status_snapshot=lambda: snapshot,
        execute_action=execute_action,
        toggle_setting=lambda name: True,
        print_fn=outputs.append,
    )

    assert "start-session" in actions
    assert "end-session" in actions
    assert any("History (press h or Esc to close)" in output for output in outputs)
    assert any("Settings (press s or Esc to close)" in output for output in outputs)
