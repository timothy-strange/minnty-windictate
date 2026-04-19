import importlib

import minnty_windictate.config as config


def test_windows_paths_follow_appdata_conventions(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))

    reloaded = importlib.reload(config)
    try:
        assert reloaded.CONFIG_DIR == tmp_path / "Roaming" / "minnty-windictate" / "Config"
        assert reloaded.CACHE_DIR == tmp_path / "Local" / "minnty-windictate" / "Cache"
        assert reloaded.DATA_DIR == tmp_path / "Local" / "minnty-windictate" / "Data"
        assert reloaded.RECORD_DIR == reloaded.DATA_DIR / "recordings"
        assert reloaded.SETTINGS_STATE_PATH == reloaded.CONFIG_DIR / "settings.json"
    finally:
        importlib.reload(config)


def test_session_config_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("MINNTY_WINDICTATE_MODEL", "distil-large-v3")
    monkeypatch.setenv("MINNTY_WINDICTATE_DEVICE", "cpu")
    monkeypatch.setenv("MINNTY_WINDICTATE_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("MINNTY_WINDICTATE_BEAM_SIZE", "3")
    monkeypatch.setenv("MINNTY_WINDICTATE_LANGUAGE", "en")

    loaded = config.session_config()

    assert loaded.model_path.endswith("distil-large-v3")
    assert loaded.device == "cpu"
    assert loaded.compute_type == "int8"
    assert loaded.beam_size == 3
    assert loaded.language == "en"


def test_default_model_path_uses_documents_whisper(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "resolve_documents_dir", lambda: tmp_path / "Documents")

    assert config.resolve_model_path() == tmp_path / "Documents" / "whisper" / "faster-whisper-large-v3"


def test_session_config_rejects_invalid_beam_size(monkeypatch):
    monkeypatch.setenv("MINNTY_WINDICTATE_BEAM_SIZE", "zero")

    try:
        config.session_config()
    except RuntimeError as exc:
        assert "MINNTY_WINDICTATE_BEAM_SIZE" in str(exc)
    else:
        raise AssertionError("Expected invalid beam size to raise RuntimeError")
