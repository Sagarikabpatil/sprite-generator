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


def test_extract_video_frames_preserves_alpha_when_video_frames_include_it(monkeypatch, tmp_path: Path):
    frame = np.zeros((2, 3, 4), dtype=np.uint8)
    frame[:] = (10, 20, 30, 70)
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: FakeCapture([frame]))
    video_path = tmp_path / "alpha-video.mp4"
    video_path.touch()

    paths = extract_video_frames(video_path, tmp_path / "alpha-frames", 1)

    with Image.open(paths[0]) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (30, 20, 10, 70)


def test_extract_video_frames_does_not_overwrite_prior_generation(monkeypatch, tmp_path: Path):
    first_generation = [np.full((2, 3, 3), 10, dtype=np.uint8)]
    second_generation = [np.full((2, 3, 3), 200, dtype=np.uint8)]
    captures = iter((first_generation, second_generation))
    monkeypatch.setattr(cv2, "VideoCapture", lambda _: FakeCapture(next(captures)))
    video_path = tmp_path / "video.mp4"
    video_path.touch()
    output_dir = tmp_path / "frames"

    first_paths = extract_video_frames(video_path, output_dir, 1)
    second_paths = extract_video_frames(video_path, output_dir, 1)

    assert first_paths[0] != second_paths[0]
    with Image.open(first_paths[0]) as first_image:
        assert first_image.getpixel((0, 0)) == (10, 10, 10, 255)
    with Image.open(second_paths[0]) as second_image:
        assert second_image.getpixel((0, 0)) == (200, 200, 200, 255)
