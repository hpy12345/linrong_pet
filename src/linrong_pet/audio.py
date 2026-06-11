from __future__ import annotations

import winsound
from pathlib import Path


class AudioPlayer:
    def __init__(self, audio_dir: Path) -> None:
        self.audio_dir = audio_dir
        self.muted = False

    def play(self, filename: str) -> None:
        if self.muted:
            return
        path = self.audio_dir / filename
        if not path.exists():
            return
        winsound.PlaySound(
            str(path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )

    def stop(self) -> None:
        winsound.PlaySound(None, 0)

