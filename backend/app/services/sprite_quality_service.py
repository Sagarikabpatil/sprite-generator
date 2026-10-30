
"""Analyze sprite sheets and animation frames for basic quality issues."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


def analyze_sprite_sheet(
    image_path: str | Path,
    frame_width: int | None = None,
    frame_height: int | None = None,
) -> dict[str, Any]:
    """Inspect a sprite sheet's dimensions, transparency, and frame layout."""
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError("The sprite sheet was not found.")

    try:
        with Image.open(path) as source:
            image = source.convert("RGBA")
    except Exception as exc:
        raise ValueError("The file is not a readable image.") from exc

    width, height = image.size
    alpha = image.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    alpha_histogram = alpha.histogram()
    total_pixels = width * height
    transparent_pixels = alpha_histogram[0]
    opaque_pixels = alpha_histogram[255]
    partially_transparent_pixels = (
        total_pixels - transparent_pixels - opaque_pixels
    )

    report: dict[str, Any] = {
        "file_name": path.name,
        "image_width": width,
        "image_height": height,
        "image_format": "RGBA",
        "has_transparency": alpha_min < 255,
        "fully_transparent_pixels": transparent_pixels,
        "partially_transparent_pixels": partially_transparent_pixels,
        "opaque_pixels": opaque_pixels,
        "transparent_pixel_percentage": round(
            transparent_pixels / total_pixels * 100, 2
        ),
        "warnings": [],
        "frame_analysis": None,
    }

    warnings: list[str] = report["warnings"]

    if width == 0 or height == 0:
        warnings.append("The image has invalid dimensions.")
        return report

    if alpha_max == 0:
        warnings.append("The image is fully transparent.")
    elif transparent_pixels == 0:
        warnings.append(
            "No fully transparent pixels detected; check whether the background is intentional."
        )

    if (frame_width is None) != (frame_height is None):
        warnings.append(
            "Provide both frame_width and frame_height to analyze the frame grid."
        )
    elif frame_width is not None and frame_height is not None:
        if frame_width <= 0 or frame_height <= 0:
            raise ValueError("Frame dimensions must be positive integers.")

        columns = width // frame_width
        rows = height // frame_height
        remainder_width = width % frame_width
        remainder_height = height % frame_height

        if remainder_width or remainder_height:
            warnings.append(
                "Sprite sheet dimensions are not evenly divisible by the frame size."
            )

        frames: list[dict[str, Any]] = []
        empty_frames = 0

        for row in range(rows):
            for column in range(columns):
                left = column * frame_width
                top = row * frame_height
                frame = image.crop(
                    (left, top, left + frame_width, top + frame_height)
                )
                frame_alpha = frame.getchannel("A")
                alpha_bounds = frame_alpha.getbbox()
                is_empty = alpha_bounds is None

                if is_empty:
                    empty_frames += 1

                frames.append(
                    {
                        "index": row * columns + column,
                        "row": row,
                        "column": column,
                        "is_empty": is_empty,
                        "content_bounds": list(alpha_bounds)
                        if alpha_bounds
                        else None,
                    }
                )

        report["frame_analysis"] = {
            "frame_width": frame_width,
            "frame_height": frame_height,
            "rows": rows,
            "columns": columns,
            "frame_count": len(frames),
            "empty_frame_count": empty_frames,
            "frames": frames,
        }

        if empty_frames:
            warnings.append(f"Found {empty_frames} fully transparent frame(s).")

    return report


def compare_sprite_frames(
    frame_paths: list[str | Path],
) -> dict[str, Any]:
    """Compare frame dimensions and approximate visual differences."""
    if not frame_paths:
        raise ValueError("At least one frame is required.")

    images: list[Image.Image] = []

    try:
        for frame_path in frame_paths:
            path = Path(frame_path)
            if not path.is_file():
                raise FileNotFoundError(f"Frame not found: {path.name}")

            with Image.open(path) as source:
                images.append(source.convert("RGBA").copy())

        dimensions = [list(image.size) for image in images]
        same_dimensions = len({tuple(size) for size in dimensions}) == 1

        report: dict[str, Any] = {
            "frame_count": len(images),
            "dimensions": dimensions,
            "consistent_dimensions": same_dimensions,
            "frames": [],
            "warnings": [],
        }

        if not same_dimensions:
            report["warnings"].append(
                "Frames have inconsistent dimensions."
            )
            return report

        reference = images[0]
        for index, image in enumerate(images):
            difference = ImageChops.difference(reference, image)
            difference_stat = ImageStat.Stat(difference)
            mean_difference = sum(difference_stat.mean) / len(
                difference_stat.mean
            )

            report["frames"].append(
                {
                    "index": index,
                    "mean_difference_from_first_frame": round(
                        mean_difference, 3
                    ),
                    "identical_to_first_frame": mean_difference == 0,
                }
            )

        if all(item["identical_to_first_frame"] for item in report["frames"]):
            report["warnings"].append(
                "All frames are identical; verify that animation was generated."
            )

        return report
    finally:
        for image in images:
            image.close()
