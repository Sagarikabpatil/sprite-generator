"""Service-layer utilities for image upload processing workflows.

This module coordinates the image pipeline for uploaded character assets and
provides a reusable entry point for the FastAPI application layer.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from fastapi import UploadFile

try:
    from app.preprocessing.background import remove_background
    from app.preprocessing.preprocess import preprocess_character
except ImportError:
    from preprocessing.background import remove_background
    from preprocessing.preprocess import preprocess_character


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
    upload_folder = "app/uploads"
    processed_folder = "app/processed"

    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(processed_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    output_filename = f"no_bg_{os.path.splitext(file.filename)[0]}.png"
    output_path = os.path.join(upload_folder, output_filename)
    remove_background(file_path, output_path)

    processed_filename = f"processed_{os.path.splitext(file.filename)[0]}.png"
    processed_path = os.path.join(processed_folder, processed_filename)
    preprocess_character(output_path, processed_path)

    return {
        "original": f"http://127.0.0.1:8000/uploads/{file.filename}",
        "removed": f"http://127.0.0.1:8000/uploads/{output_filename}",
        "processed": f"http://127.0.0.1:8000/processed/{processed_filename}",
    }
