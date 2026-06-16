import json

from linrong_pet.settings import PetSettings, SettingsStore
from linrong_pet.settings import (
    DEFAULT_ATTENTION_DELAY_MINUTES,
    DEFAULT_ATTENTION_REPEAT_MINUTES,
    MAX_ATTENTION_DELAY_MINUTES,
    MIN_ATTENTION_DELAY_MINUTES,
)


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    expected = PetSettings(
        roaming_enabled=False,
        muted=True,
        pet_height=400,
        autostart_enabled=True,
        attention_enabled=False,
        attention_delay_minutes=12,
        attention_repeat_minutes=8,
        last_x=123,
        last_y=456,
    )
    store.save(expected)
    assert store.load() == expected
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_invalid_settings_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"pet_height": 999, "last_x": true, "roaming_enabled": 0, '
        '"attention_delay_minutes": 1, "attention_repeat_minutes": 99999}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.pet_height == 320
    assert loaded.last_x is None
    assert loaded.roaming_enabled is False
    assert loaded.attention_delay_minutes == MIN_ATTENTION_DELAY_MINUTES
    assert loaded.attention_repeat_minutes == MAX_ATTENTION_DELAY_MINUTES


def test_attention_settings_default_for_legacy_files(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"pet_height": 320}', encoding="utf-8")
    loaded = SettingsStore(path).load()

    assert loaded.attention_enabled is True
    assert loaded.attention_delay_minutes == DEFAULT_ATTENTION_DELAY_MINUTES
    assert loaded.attention_repeat_minutes == DEFAULT_ATTENTION_REPEAT_MINUTES


def test_attention_settings_migrate_legacy_seconds_to_minutes(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"attention_delay_seconds": 301, "attention_repeat_seconds": 180}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()

    assert loaded.attention_delay_minutes == 6
    assert loaded.attention_repeat_minutes == MIN_ATTENTION_DELAY_MINUTES

