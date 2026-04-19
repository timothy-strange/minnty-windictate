from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "minnty-windictate"


def local_app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Roaming"


def cache_dir() -> Path:
    return local_app_data_dir() / APP_NAME / "Cache"


def data_dir() -> Path:
    return local_app_data_dir() / APP_NAME / "Data"


def config_dir() -> Path:
    return app_data_dir() / APP_NAME / "Config"
