"""Service-layer utilities for image upload processing workflows.

This module coordinates the image pipeline for uploaded character assets and
provides a reusable entry point for the FastAPI application layer.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import UploadFile

try:
    from app.preprocessing.background import remove_background
    from app.preprocessing.preprocess import preprocess_character
except ImportError:
    from preprocessing.background import remove_background
    from preprocessing.preprocess import preprocess_character


APP_DIR = Path(__file__).resolve().parents[1]
UPLOAD_FOLDER = APP_DIR / "uploads"
PROCESSED_FOLDER = APP_DIR / "processed"


def process_image_path(input_path: str | Path, source_name: str) -> dict[str, str | Path]:
    """Run background removal and preprocessing for an existing image file."""
    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source character image was not found: {source_path}")

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)

    stem = Path(source_name).stem
    removed_filename = f"no_bg_{stem}.png"
    processed_filename = f"processed_{stem}.png"
    removed_path = UPLOAD_FOLDER / removed_filename
    processed_path = PROCESSED_FOLDER / processed_filename

    remove_background(str(source_path), str(removed_path))
    preprocess_character(str(removed_path), str(processed_path))

    return {
        "removed_path": removed_path,
        "processed_path": processed_path,
        "removed_url": f"http://127.0.0.1:8000/uploads/{removed_filename}",
        "processed_url": f"http://127.0.0.1:8000/processed/{processed_filename}",
    }


def process_uploaded_image(file: UploadFile) -> dict[str, str]:
    """Process an uploaded image through the complete backend workflow.

    The function saves the uploaded file into the configured upload directory,
    removes its background, preprocesses the character image, saves the output
    into the processed directory, and returns a dictionary matching the current
    API response payload.

    Args:
        file (UploadFile): The uploaded image file from the client.

    Returns:
        dict[str, str]: A response payload containing the original, removed, and
            processed image URLs.
    """
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_FOLDER / file.filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    processed = process_image_path(file_path, file.filename)

    return {
        "original": f"http://127.0.0.1:8000/uploads/{file.filename}",
        "removed": str(processed["removed_url"]),
        "processed": str(processed["processed_url"]),
    }
