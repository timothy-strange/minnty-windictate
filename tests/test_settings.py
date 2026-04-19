from minnty_windictate.settings import default_settings


def test_default_settings_include_hotkey():
    settings = default_settings()

    assert settings.hotkey
    assert settings.cancel_hotkey
    assert settings.sample_rate == 16000
    assert settings.auto_paste is True


def test_update_settings_persists(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))

    import importlib
    import minnty_windictate.config as config
    import minnty_windictate.settings as settings_module

    importlib.reload(config)
    importlib.reload(settings_module)
    try:
        saved = settings_module.update_settings(
            record_seconds=12.5,
            hotkey="ctrl+shift+r",
            cancel_hotkey="ctrl+shift+backspace",
        )

        assert saved.input_device is None
        assert saved.sample_rate == 16000
        assert saved.channels == 1
        assert saved.record_seconds == 12.5
        assert saved.auto_paste is True
        assert saved.hotkey == "ctrl+shift+r"
        assert saved.cancel_hotkey == "ctrl+shift+backspace"
        assert settings_module.read_settings().record_seconds == 12.5
    finally:
        importlib.reload(config)
        importlib.reload(settings_module)
