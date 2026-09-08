from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.sprite.video_frames import extract_video_frames


class FakeCapture:
    def __init__(self, frames):
        self.frames = iter(frames)

    def isOpened(self):
        return True

    def read(self):
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self):
        pass


def test_extract_video_frames_selects_deterministic_even_indices(monkeypatch, tmp_path: Path):
    frames = [np.full((2, 3, 3), value, dtype=np.uint8) for value in range(16)]
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: FakeCapture(frames))
    video_path = tmp_path / "video.mp4"
    video_path.touch()

    paths = extract_video_frames(video_path, tmp_path / "frames", 8)

    assert len(paths) == 8
    assert [Image.open(path).getpixel((0, 0))[0] for path in paths] == [0, 2, 4, 6, 9, 11, 13, 15]
    assert all(Image.open(path).mode == "RGBA" for path in paths)
