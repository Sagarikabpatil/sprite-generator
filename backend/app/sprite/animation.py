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
    previous_signature: bytes | None = None
    for frame_path in frame_paths:
        path = Path(frame_path)
        if not path.is_file():
            raise FileNotFoundError(f"Generated frame was not found: {path.name}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                current_dimensions = image.size
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                rgb = rgba.convert("RGB")
                extrema = rgb.getextrema()
                signature_image = rgb.resize((32, 32), Image.Resampling.BILINEAR).convert("L")
                signature = signature_image.tobytes()
        except (OSError, ValueError) as exc:
            raise ValueError(f"Generated frame is not a readable image: {path.name}") from exc
        if dimensions is None:
            dimensions = current_dimensions
        elif current_dimensions != dimensions:
            raise ValueError("Generated frames have inconsistent dimensions.")
        if alpha.getbbox() is None or all(high - low <= 2 for low, high in extrema):
            raise ValueError(f"Generated animation contains a blank frame: {path.name}")
        if previous_signature is not None:
            mean_difference = sum(
                abs(previous - current)
                for previous, current in zip(previous_signature, signature)
            ) / len(signature)
            if mean_difference < 0.15:
                raise ValueError("Generated animation contains consecutive nearly identical frames.")
        alpha.close()
        rgba.close()
        rgb.close()
        signature_image.close()
        previous_signature = signature
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
