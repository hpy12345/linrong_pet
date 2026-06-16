from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import settings_path


ALLOWED_HEIGHTS = (240, 320, 400)
DEFAULT_ATTENTION_DELAY_MINUTES = 5
DEFAULT_ATTENTION_REPEAT_MINUTES = 5
MIN_ATTENTION_DELAY_MINUTES = 5
MAX_ATTENTION_DELAY_MINUTES = 1440


@dataclass(slots=True)
class PetSettings:
    version: int = 1
    roaming_enabled: bool = True
    muted: bool = False
    pet_height: int = 320
    autostart_enabled: bool = False
    attention_enabled: bool = True
    attention_delay_minutes: int = DEFAULT_ATTENTION_DELAY_MINUTES
    attention_repeat_minutes: int = DEFAULT_ATTENTION_REPEAT_MINUTES
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
            attention_enabled=bool(raw.get("attention_enabled", True)),
            attention_delay_minutes=_attention_minutes_from_settings(
                raw,
                "attention_delay_minutes",
                "attention_delay_seconds",
                DEFAULT_ATTENTION_DELAY_MINUTES,
            ),
            attention_repeat_minutes=_attention_minutes_from_settings(
                raw,
                "attention_repeat_minutes",
                "attention_repeat_seconds",
                DEFAULT_ATTENTION_REPEAT_MINUTES,
            ),
            last_x=_optional_int(raw.get("last_x")),
            last_y=_optional_int(raw.get("last_y")),
        )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def clamp_attention_minutes(value: Any, default: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        return default
    return max(
        MIN_ATTENTION_DELAY_MINUTES,
        min(MAX_ATTENTION_DELAY_MINUTES, value),
    )


def _attention_minutes_from_settings(
    raw: dict[str, Any],
    minutes_key: str,
    legacy_seconds_key: str,
    default: int,
) -> int:
    if minutes_key in raw:
        return clamp_attention_minutes(raw.get(minutes_key), default)
    legacy_seconds = raw.get(legacy_seconds_key)
    if isinstance(legacy_seconds, int) and not isinstance(legacy_seconds, bool):
        minutes = max(0, legacy_seconds + 59) // 60
        return clamp_attention_minutes(minutes, default)
    return default


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

