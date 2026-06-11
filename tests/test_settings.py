import json

from linrong_pet.settings import PetSettings, SettingsStore


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    expected = PetSettings(
        roaming_enabled=False,
        muted=True,
        pet_height=400,
        autostart_enabled=True,
        last_x=123,
        last_y=456,
    )
    store.save(expected)
    assert store.load() == expected
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_invalid_settings_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"pet_height": 999, "last_x": true, "roaming_enabled": 0}',
        encoding="utf-8",
    )
    loaded = SettingsStore(path).load()
    assert loaded.pet_height == 320
    assert loaded.last_x is None
    assert loaded.roaming_enabled is False

