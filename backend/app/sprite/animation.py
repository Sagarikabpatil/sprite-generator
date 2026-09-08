"""Validation and metadata helpers for sprite animation sequences."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image


def validate_generated_frames(frame_paths: list[str]) -> list[str]:
    """Verify frame files are readable images with consistent dimensions."""
    if not frame_paths:
        raise ValueError("No generated animation frames were returned.")

    validated: list[str] = []
    dimensions = None
    for frame_path in frame_paths:
        path = Path(frame_path)
        if not path.is_file():
            raise FileNotFoundError(f"Generated frame was not found: {path.name}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                current_dimensions = image.size
        except (OSError, ValueError) as exc:
            raise ValueError(f"Generated frame is not a readable image: {path.name}") from exc
        if dimensions is None:
            dimensions = current_dimensions
        elif current_dimensions != dimensions:
            raise ValueError("Generated frames have inconsistent dimensions.")
        validated.append(str(path))
    return validated


def order_frames(frame_paths: list[str]) -> list[str]:
    """Order frames by numeric suffix, then by filename."""
    def frame_sort_key(frame_path: str) -> tuple[int, str]:
        name = Path(frame_path).stem
        match = re.search(r"(?:frame|_)(\d+)$", name, re.IGNORECASE)
        return (int(match.group(1)) if match else 0, name)

    return sorted(frame_paths, key=frame_sort_key)


def create_animation_sequence(action: str, frame_paths: list[str]) -> dict[str, object]:
    """Validate, order, and describe one animation sequence."""
    ordered_frames = order_frames(validate_generated_frames(frame_paths))
    return {"action": action, "frame_count": len(ordered_frames), "frames": ordered_frames}


def build_animation(frames: list[str], action: str = "unknown") -> dict[str, object]:
    """Backward-compatible name for creating an animation sequence."""
    return create_animation_sequence(action, frames)
