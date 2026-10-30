"""Deterministic OpenCV video frame extraction for sprite generation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import cv2


def extract_video_frames(video_path: Path, output_dir: Path, frame_count: int) -> list[str]:
    """Extract evenly distributed RGBA PNG frames from a generated video."""
    if frame_count < 1:
        raise ValueError("frame_count must be at least 1.")
    if not video_path.is_file():
        raise FileNotFoundError(f"Generated video was not found: {video_path.name}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Generated video could not be opened: {video_path.name}")

    frames = []
    try:
        while True:
            has_frame, frame = capture.read()
            if not has_frame:
                break
            if frame is None or frame.size == 0:
                continue
            if frame.ndim != 3 or frame.shape[2] not in (3, 4):
                raise ValueError("Generated video contains an unsupported frame format.")
            conversion = cv2.COLOR_BGRA2RGBA if frame.shape[2] == 4 else cv2.COLOR_BGR2RGBA
            frames.append(cv2.cvtColor(frame, conversion))
    finally:
        capture.release()

    if len(frames) < frame_count:
        raise ValueError(
            f"Generated video contains only {len(frames)} usable frames; "
            f"at least {frame_count} are required."
        )

    selected_indices = [
        round(index * (len(frames) - 1) / (frame_count - 1))
        if frame_count > 1
        else 0
        for index in range(frame_count)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[str] = []
    generation_id = uuid4().hex
    for index, frame_index in enumerate(selected_indices):
        output_path = output_dir / f"frame_{generation_id}_{index:03d}.png"
        if not cv2.imwrite(str(output_path), cv2.cvtColor(frames[frame_index], cv2.COLOR_RGBA2BGRA)):
            raise OSError(f"Failed to save extracted frame: {output_path.name}")
        output_paths.append(str(output_path))
    return output_paths
