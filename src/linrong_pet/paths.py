from __future__ import annotations

import os
import sys
from pathlib import Path


APP_ID = "LinRongPet"


def package_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent


def asset_path(*parts: str) -> Path:
    return package_root().joinpath("assets", *parts)


def settings_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / APP_ID


def settings_path() -> Path:
    return settings_dir() / "settings.json"

