from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import settings_path


ALLOWED_HEIGHTS = (240, 320, 400)


@dataclass(slots=True)
class PetSettings:
    version: int = 1
    roaming_enabled: bool = True
    muted: bool = False
    pet_height: int = 320
    autostart_enabled: bool = False
    last_x: int | None = None
    last_y: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PetSettings":
        height = raw.get("pet_height", 320)
        if height not in ALLOWED_HEIGHTS:
            height = 320
        return cls(
            version=1,
            roaming_enabled=bool(raw.get("roaming_enabled", True)),
            muted=bool(raw.get("muted", False)),
            pet_height=height,
            autostart_enabled=bool(raw.get("autostart_enabled", False)),
            last_x=_optional_int(raw.get("last_x")),
            last_y=_optional_int(raw.get("last_y")),
        )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()

    def load(self) -> PetSettings:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return PetSettings()
        return PetSettings.from_dict(raw if isinstance(raw, dict) else {})

    def save(self, settings: PetSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="settings-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(asdict(settings), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

