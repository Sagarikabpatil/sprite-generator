"""Build transparent PNG sprite sheets from animation frames."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image


def build_sprite_sheet(frame_paths: list[str], output_path: str, columns: int = 4) -> str:
    """Arrange equally sized RGBA frames into a transparent grid."""
    if not frame_paths:
        raise ValueError("Cannot build a sprite sheet without frames.")
    if columns < 1:
        raise ValueError("columns must be at least 1.")

    images: list[Image.Image] = []
    try:
        for frame_path in frame_paths:
            images.append(Image.open(frame_path).convert("RGBA"))
        frame_size = images[0].size
        if any(image.size != frame_size for image in images[1:]):
            raise ValueError("Cannot build a sprite sheet from inconsistent frame dimensions.")

        rows = math.ceil(len(images) / columns)
        sheet = Image.new("RGBA", (frame_size[0] * columns, frame_size[1] * rows), (0, 0, 0, 0))
        for index, image in enumerate(images):
            position = ((index % columns) * frame_size[0], (index // columns) * frame_size[1])
            sheet.paste(image, position, image)

        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(destination, format="PNG")
        return str(destination)
    except OSError as exc:
        raise RuntimeError(f"Failed to build sprite sheet: {exc}") from exc
    finally:
        for image in images:
            image.close()


def build_sheet(frames: list[str], output_path: str, columns: int = 4) -> str:
    """Backward-compatible name for building a sprite sheet."""
    return build_sprite_sheet(frames, output_path, columns)
