"""Dataset validation utilities for sprite-related assets."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError


def validate_image(image: Any) -> bool:
    """Validate that an image is openable, visually meaningful, and within reasonable dimensions."""
    if image is None:
        return False

    try:
        if isinstance(image, bytes):
            image_obj = Image.open(io.BytesIO(image))
        elif isinstance(image, Image.Image):
            image_obj = image
        else:
            return False

        image_obj.load()
        mode = image_obj.mode
        if mode not in {"RGB", "RGBA", "L", "P", "LA"}:
            return False

        width, height = image_obj.size
        if width <= 0 or height <= 0:
            return False
        if width < 32 or height < 32:
            return False
        if width > 2048 or height > 2048:
            return False
        if max(width / height, height / width) > 4:
            return False

        array = np.asarray(image_obj.convert("RGBA"))
        if array.size == 0:
            return False

        alpha = array[:, :, 3]
        rgb = array[:, :, :3]
        empty_pixels = np.all(rgb < 5, axis=2) & (alpha < 5)
        if empty_pixels.all():
            return False

        return True
    except (TypeError, ValueError, UnidentifiedImageError, OSError):
        return False


def validate_caption(caption: Any) -> bool:
    """Validate that a caption exists and is meaningful text."""
    if not isinstance(caption, str):
        return False

    cleaned = caption.strip()
    if not cleaned:
        return False
    if len(cleaned) < 3:
        return False
    if len(cleaned) > 2000:
        return False

    return True


def validate_dataset(data: Any) -> bool:
    """Check whether a dataset-like object contains usable image/caption pairs."""
    if data is None:
        return False
    if not hasattr(data, "__len__"):
        return False

    for sample in data:
        image = sample.get("image")
        caption = sample.get("text") or sample.get("caption") or sample.get("prompt")
        if not validate_image(image):
            return False
        if not validate_caption(caption):
            return False

    return True

