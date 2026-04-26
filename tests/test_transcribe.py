import pytest

from minnty_windictate import transcribe
from minnty_windictate.transcribe import ensure_supported_whisper_runtime


def test_python_314_or_newer_is_rejected(monkeypatch):
    monkeypatch.setattr("minnty_windictate.transcribe.whisper_runtime_version", lambda: (3, 14, 0))

    with pytest.raises(RuntimeError) as exc:
        ensure_supported_whisper_runtime()

    assert "Python 3.12 or 3.13" in str(exc.value)


def test_configure_runtime_library_path_prepends_app_local_nvidia_libs(monkeypatch, tmp_path):
    libs_dir = tmp_path / "libs" / "nvidia"
    libs_dir.mkdir(parents=True)
    monkeypatch.setattr(transcribe, "NVIDIA_LIBS_DIR", libs_dir)
    monkeypatch.setattr(transcribe, "_NVIDIA_DLL_DIRECTORY_HANDLE", None)
    monkeypatch.setenv("PATH", "C:\\Windows")

    transcribe.configure_runtime_library_path()
    transcribe.configure_runtime_library_path()

    path_parts = [part for part in transcribe.os.environ["PATH"].split(transcribe.os.pathsep) if part]
    assert path_parts[0] == str(libs_dir)
    assert path_parts.count(str(libs_dir)) == 1
