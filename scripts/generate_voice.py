from __future__ import annotations

import argparse
import asyncio
import math
import sys
import tempfile
import wave
from array import array
from pathlib import Path

import edge_tts
import miniaudio


LINES = {
    "hello.wav": "你好呀，我是林榕。",
    "happy.wav": "见到你真开心。",
    "found.wav": "呀，你找到我啦。",
    "poked.wav": "别一直戳我嘛。",
    "company.wav": "需要我陪你一会儿吗？",
    "rest.wav": "记得让眼睛休息一下哦。",
    "love.wav": "爱你哦",
}


VOICE = "zh-CN-XiaoxiaoNeural"
RATE = "+2%"
PITCH = "+6Hz"
VOLUME = "-2%"
SAMPLE_RATE = 24000


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
        for filename, text in LINES.items():
            if selected is not None and filename not in selected:
                continue
            media_path = temp_dir / filename.replace(".wav", ".mp3")
            communicator = edge_tts.Communicate(
                text,
                VOICE,
                rate=RATE,
                volume=VOLUME,
                pitch=PITCH,
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
            samples = normalized_samples(decoded.samples, SAMPLE_RATE)
            output_path = output_dir / filename
            with wave.open(str(output_path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(SAMPLE_RATE)
                stream.writeframes(samples.tobytes())
            print(f"generated {output_path.name} with {VOICE}")


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
