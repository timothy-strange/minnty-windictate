from minnty_windictate.console import console_available_actions, render_console, run_console


def test_console_actions_match_linux_style_states():
    idle_actions = console_available_actions(recording_status="idle", session_status="idle")
    recording_actions = console_available_actions(recording_status="recording", session_status="ready")
    transcribing_actions = console_available_actions(recording_status="transcribing", session_status="ready")

    assert ("m", "Start session and load model", "start-session") in idle_actions
    assert ("q", "Quit and unload", "quit-console") in idle_actions
    assert ("h", "History", "history") in idle_actions
    assert ("s", "Settings", "settings") in idle_actions
    assert ("c", "Cancel recording", "cancel-recording") in recording_actions
    assert all(action[0] != "c" for action in transcribing_actions)


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
        key_available_fn=lambda: True,
        sleep_fn=lambda seconds: None,
        print_fn=outputs.append,
    )

    assert "start-session" in actions
    assert "end-session" in actions
    assert any("History (press h or Esc to close)" in output for output in outputs)
    assert any("Settings (press s or Esc to close)" in output for output in outputs)


def test_run_console_live_refreshes_without_keypress():
    outputs: list[str] = []
    states = [
        {
            "recording_status": "idle",
            "session_status": "idle",
            "status_line": "Idle",
            "last_transcription_line": "None",
            "history": [],
            "save_transcriptions_to_file": False,
        },
        {
            "recording_status": "recording",
            "session_status": "ready",
            "status_line": "Recording",
            "last_transcription_line": "None",
            "history": [],
            "save_transcriptions_to_file": False,
        },
    ]
    counter = {"index": 0}

    def status_snapshot():
        index = min(counter["index"], len(states) - 1)
        return states[index]

    def sleep_once(_seconds):
        counter["index"] += 1
        if counter["index"] > 1:
            raise KeyboardInterrupt

    try:
        run_console(
            status_snapshot=status_snapshot,
            execute_action=lambda action: "ok",
            toggle_setting=lambda name: False,
            key_available_fn=lambda: False,
            sleep_fn=sleep_once,
            print_fn=outputs.append,
        )
    except KeyboardInterrupt:
        pass

    assert any("Status: Idle" in output for output in outputs)
    assert any("Status: Recording" in output for output in outputs)
