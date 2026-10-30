"""Service-layer utilities for image upload processing workflows.

This module coordinates the image pipeline for uploaded character assets and
provides a reusable entry point for the FastAPI application layer.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

try:
    from app.preprocessing.background import remove_background
    from app.preprocessing.preprocess import preprocess_character
except ImportError:
    from preprocessing.background import remove_background
    from preprocessing.preprocess import preprocess_character


APP_DIR = Path(__file__).resolve().parents[1]
UPLOAD_FOLDER = APP_DIR.parent / "uploads"
PROCESSED_FOLDER = APP_DIR / "processed"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


class ImageProcessingError(RuntimeError):
    """Raised when a supported image fails during background removal or preprocessing."""


def process_image_path(input_path: str | Path, source_name: str) -> dict[str, str | Path]:
    """Run background removal and preprocessing for an existing image file."""
    source_path = Path(input_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source character image was not found: {source_path}")
    if not source_name or Path(source_name).name != source_name or "/" in source_name or "\\" in source_name:
        raise ValueError("Unsafe image source filename.")

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)

    stem = Path(source_name).stem
    removed_filename = f"no_bg_{stem}.png"
    processed_filename = f"processed_{stem}.png"
    upload_root = UPLOAD_FOLDER.resolve()
    processed_root = PROCESSED_FOLDER.resolve()
    removed_path = (upload_root / removed_filename).resolve()
    processed_path = (processed_root / processed_filename).resolve()
    if (
        not removed_path.is_relative_to(upload_root)
        or not processed_path.is_relative_to(processed_root)
        or removed_path.exists()
        or processed_path.exists()
    ):
        raise FileExistsError("Image processing output already exists or is outside its storage directory.")

    try:
        remove_background(str(source_path), str(removed_path))
        preprocess_character(str(removed_path), str(processed_path))
    except Exception as exc:
        for output_path in (removed_path, processed_path):
            if output_path.is_file():
                output_path.unlink()
        raise ImageProcessingError(
            "The image was accepted but could not be processed. Try another image."
        ) from exc

    return {
        "removed_path": removed_path,
        "processed_path": processed_path,
        "removed_url": f"http://127.0.0.1:8000/uploads/{removed_filename}",
        "processed_url": f"http://127.0.0.1:8000/processed/{processed_filename}",
    }


def process_uploaded_image(file: UploadFile, *, filename: str) -> dict[str, str | Path]:
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
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("Unsafe upload filename.")
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    upload_root = UPLOAD_FOLDER.resolve()
    file_path = (upload_root / filename).resolve()
    if not file_path.is_relative_to(upload_root):
        raise ValueError("Upload path is outside its storage directory.")
    if file_path.exists():
        raise FileExistsError("Upload output already exists.")

    file.file.seek(0)
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Image uploads must be 10 MB or smaller.")

    allowed_formats = {
        ".png": "PNG",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".webp": "WEBP",
    }
    expected_format = allowed_formats.get(Path(filename).suffix.lower())
    if expected_format is None:
        raise ValueError("Upload a PNG, JPG, JPEG, or WEBP image.")
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            frame_count = getattr(image, "n_frames", 1)
            image.verify()
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError, ValueError) as exc:
        raise ValueError("The uploaded file is not a valid PNG, JPG, JPEG, or WEBP image.") from exc
    if image_format != expected_format:
        raise ValueError("The image contents do not match the selected file type.")
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions are too large to process safely.")
    if frame_count != 1:
        raise ValueError("Animated images are not supported. Upload a single-frame image.")

    with file_path.open("xb") as buffer:
        buffer.write(data)

    try:
        processed = process_image_path(file_path, filename)
    except Exception:
        if file_path.is_file():
            file_path.unlink()
        raise

    return {
        "original_path": file_path,
        "removed_path": processed["removed_path"],
        "processed_path": processed["processed_path"],
    }
