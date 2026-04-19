import importlib

import minnty_windictate.config as config
import minnty_windictate.paths as paths


def test_windows_paths_use_documents_root(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "documents_dir", lambda: tmp_path / "Documents")

    reloaded = importlib.reload(config)
    try:
        assert reloaded.APP_ROOT_DIR == tmp_path / "Documents" / "minnty-windictate"
        assert reloaded.CONFIG_DIR == reloaded.APP_ROOT_DIR / "config"
        assert reloaded.CACHE_DIR == reloaded.APP_ROOT_DIR / "runtime"
        assert reloaded.DATA_DIR == reloaded.APP_ROOT_DIR
        assert reloaded.RECORD_DIR == reloaded.APP_ROOT_DIR / "recordings"
        assert reloaded.MODEL_DIR == reloaded.APP_ROOT_DIR / "models"
        assert reloaded.TRANSCRIPTIONS_DIR == reloaded.APP_ROOT_DIR / "transcriptions"
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


def test_default_model_path_uses_documents_app_root(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "documents_dir", lambda: tmp_path / "Documents")

    reloaded = importlib.reload(config)
    try:
        assert reloaded.resolve_model_path() == tmp_path / "Documents" / "minnty-windictate" / "models" / "faster-whisper-large-v3"
    finally:
        importlib.reload(config)


def test_session_config_rejects_invalid_beam_size(monkeypatch):
    monkeypatch.setenv("MINNTY_WINDICTATE_BEAM_SIZE", "zero")

    try:
        config.session_config()
    except RuntimeError as exc:
        assert "MINNTY_WINDICTATE_BEAM_SIZE" in str(exc)
    else:
        raise AssertionError("Expected invalid beam size to raise RuntimeError")
