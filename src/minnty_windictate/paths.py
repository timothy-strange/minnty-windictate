from __future__ import annotations

from pathlib import Path


APP_NAME = "minnty-windictate"


def documents_dir() -> Path:
    return Path.home() / "Documents"


def app_root_dir() -> Path:
    return documents_dir() / APP_NAME


def cache_dir() -> Path:
    return app_root_dir() / "runtime"


def data_dir() -> Path:
    return app_root_dir()


def config_dir() -> Path:
    return app_root_dir() / "config"
