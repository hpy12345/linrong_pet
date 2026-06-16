from __future__ import annotations

import argparse
import asyncio
import math
import sys
import tempfile
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

import edge_tts
import miniaudio


@dataclass(frozen=True, slots=True)
class VoiceLine:
    text: str
    rate: str
    pitch: str
    volume: str = "-2%"


LINES = {
    "hello.wav": VoiceLine("你好呀，我是林榕。", "-3%", "+0Hz"),
    "found.wav": VoiceLine("呀，你找到我啦。", "-2%", "+1Hz"),
    "poked.wav": VoiceLine("别一直戳我嘛。", "-4%", "+1Hz"),
    "company.wav": VoiceLine("需要我陪你一会儿吗？", "-9%", "-1Hz"),
    "rest.wav": VoiceLine("记得让眼睛休息一下哦。", "-10%", "-1Hz"),
    "love.wav": VoiceLine("爱你哦", "-4%", "+1Hz"),
    "hug.wav": VoiceLine("主人，来陪我玩嘛", "-6%", "+1Hz"),
}


VOICE = "zh-CN-XiaoxiaoNeural"
SAMPLE_RATE = 24000


def trim_silence(samples: array, sample_rate: int) -> array:
    active = [
        index
        for index, sample in enumerate(samples)
        if abs(sample) >= 250
    ]
    if not active:
        raise ValueError("generated voice contains no audible speech")
    start = max(0, active[0] - round(sample_rate * 0.10))
    end = min(len(samples), active[-1] + 1 + round(sample_rate * 0.18))
    return array("h", samples[start:end])


def normalized_samples(samples: array, sample_rate: int) -> array:
    peak = max((abs(sample) for sample in samples), default=0)
    if peak == 0:
        raise ValueError("generated voice is silent")
    target_peak = round(32767 * 10 ** (-1.5 / 20))
    gain = min(1.8, target_peak / peak)
    result = array("h", (round(sample * gain) for sample in samples))

    fade_frames = min(round(sample_rate * 0.025), len(result) // 2)
    for index in range(fade_frames):
        factor = math.sin((index + 1) / fade_frames * math.pi / 2) ** 2
        result[index] = round(result[index] * factor)
        result[-index - 1] = round(result[-index - 1] * factor)
    return result


async def synthesize(
    output_dir: Path,
    selected: set[str] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="linrong-voice-") as temp:
        temp_dir = Path(temp)
        for filename, line in LINES.items():
            if selected is not None and filename not in selected:
                continue
            media_path = temp_dir / filename.replace(".wav", ".mp3")
            communicator = edge_tts.Communicate(
                line.text,
                VOICE,
                rate=line.rate,
                volume=line.volume,
                pitch=line.pitch,
                connect_timeout=20,
                receive_timeout=60,
            )
            await communicator.save(str(media_path))
            decoded = miniaudio.decode_file(
                str(media_path),
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=1,
                sample_rate=SAMPLE_RATE,
            )
            samples = normalized_samples(
                trim_silence(decoded.samples, SAMPLE_RATE),
                SAMPLE_RATE,
            )
            output_path = output_dir / filename
            with wave.open(str(output_path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(SAMPLE_RATE)
                stream.writeframes(samples.tobytes())
            print(f"generated {output_path.name} with {VOICE}")
    if selected is None:
        for path in output_dir.glob("*.wav"):
            if path.name not in LINES:
                path.unlink()
                print(f"removed stale voice asset {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("src/linrong_pet/assets/audio"),
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=sorted(LINES),
        help="Generate only the selected WAV file; may be repeated.",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(synthesize(args.output_dir, set(args.only) if args.only else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
