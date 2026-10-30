from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.sprite.animation import create_animation_sequence, validate_generated_frames


def create_moving_frame(path: Path, offset: int) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 255))
    ImageDraw.Draw(image).rectangle((8 + offset, 12, 24 + offset, 44), fill=(220, 50, 90, 255))
    image.save(path)


def test_frame_validation_accepts_distinct_nonblank_frames(tmp_path):
    first = tmp_path / "frame_000.png"
    second = tmp_path / "frame_001.png"
    create_moving_frame(first, 0)
    create_moving_frame(second, 8)

    sequence = create_animation_sequence("walk", [str(first), str(second)])

    assert sequence["frame_count"] == 2
    assert sequence["frames"] == [str(first), str(second)]


def test_frame_validation_rejects_blank_frames(tmp_path):
    blank = tmp_path / "frame_000.png"
    Image.new("RGBA", (32, 32), (0, 0, 0, 255)).save(blank)

    with pytest.raises(ValueError, match="blank frame"):
        validate_generated_frames([str(blank)])


def test_frame_validation_rejects_nearly_identical_consecutive_frames(tmp_path):
    first = tmp_path / "frame_000.png"
    second = tmp_path / "frame_001.png"
    create_moving_frame(first, 0)
    create_moving_frame(second, 0)

    with pytest.raises(ValueError, match="nearly identical"):
        validate_generated_frames([str(first), str(second)])


def test_frame_validation_rejects_inconsistent_dimensions(tmp_path):
    first = tmp_path / "frame_000.png"
    second = tmp_path / "frame_001.png"
    create_moving_frame(first, 0)
    Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(second)

    with pytest.raises(ValueError, match="inconsistent dimensions"):
        validate_generated_frames([str(first), str(second)])
