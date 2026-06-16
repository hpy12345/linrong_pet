from __future__ import annotations

from array import array
import math
import wave
from pathlib import Path

from scripts.validate_voice import validate


def test_offline_voice_assets_are_valid_mono_wav_files():
    audio_dir = (
        Path(__file__).parents[1]
        / "src"
        / "linrong_pet"
        / "assets"
        / "audio"
    )
    expected = {
        "hello.wav",
        "found.wav",
        "poked.wav",
        "company.wav",
        "rest.wav",
        "love.wav",
        "hug.wav",
    }
    assert {path.name for path in audio_dir.glob("*.wav")} == expected

    for path in audio_dir.glob("*.wav"):
        with wave.open(str(path), "rb") as stream:
            assert stream.getnchannels() == 1
            assert stream.getsampwidth() == 2
            assert stream.getframerate() >= 24000
            assert stream.getnframes() >= stream.getframerate() * 0.75
            samples = array("h", stream.readframes(stream.getnframes()))
            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            assert rms > 500
            assert max(abs(sample) for sample in samples) > 5000

    assert validate(audio_dir) == []
