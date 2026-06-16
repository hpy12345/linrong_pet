from __future__ import annotations

import argparse
import math
import wave
from array import array
from pathlib import Path


EXPECTED = {
    "hello.wav",
    "found.wav",
    "poked.wav",
    "company.wav",
    "rest.wav",
    "love.wav",
    "hug.wav",
}


def validate(audio_dir: Path) -> list[str]:
    errors: list[str] = []
    actual = {path.name for path in audio_dir.glob("*.wav")}
    if actual != EXPECTED:
        errors.append(f"voice files are {sorted(actual)}, expected {sorted(EXPECTED)}")
    for name in sorted(EXPECTED & actual):
        path = audio_dir / name
        try:
            with wave.open(str(path), "rb") as stream:
                channels = stream.getnchannels()
                sample_width = stream.getsampwidth()
                sample_rate = stream.getframerate()
                frame_count = stream.getnframes()
                samples = array("h", stream.readframes(frame_count))
        except (OSError, wave.Error) as exc:
            errors.append(f"cannot read {name}: {exc}")
            continue
        if channels != 1 or sample_width != 2:
            errors.append(f"{name} must be 16-bit mono PCM")
        if sample_rate < 24000:
            errors.append(f"{name} sample rate is below 24 kHz")
        duration = frame_count / sample_rate
        if not 0.75 <= duration <= 8.0:
            errors.append(f"{name} duration is outside 0.75-8.0 seconds")
        if not samples:
            errors.append(f"{name} contains no samples")
            continue
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        peak = max(abs(sample) for sample in samples)
        if rms <= 500 or peak <= 5000:
            errors.append(f"{name} is silent or too quiet")
        clipped = sum(abs(sample) >= 32760 for sample in samples)
        if clipped / len(samples) > 0.001:
            errors.append(f"{name} contains excessive clipping")
        active_threshold = 300
        active = [
            index
            for index, sample in enumerate(samples)
            if abs(sample) >= active_threshold
        ]
        if not active:
            errors.append(f"{name} contains no audible speech")
            continue
        leading_silence = active[0] / sample_rate
        trailing_silence = (len(samples) - active[-1] - 1) / sample_rate
        if leading_silence > 0.35:
            errors.append(f"{name} has excessive leading silence")
        if trailing_silence > 0.45:
            errors.append(f"{name} has excessive trailing silence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.audio_dir)
    if errors:
        print("\n".join(errors))
        return 1
    print("voice validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
