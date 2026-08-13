"""Export a cleaned dataset into an ImageFolder-compatible layout."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CLEAN_DIR = DATA_DIR / "clean"
IMAGES_DIR = CLEAN_DIR / "images"
METADATA_DIR = CLEAN_DIR / "metadata"


def export_clean_dataset(records: list[dict[str, Any]]) -> Path:
    """Save the cleaned dataset to backend/data/clean with image and metadata files."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    metadata_path = METADATA_DIR / "metadata.jsonl"
    if metadata_path.exists():
        metadata_path.unlink()

    for index, record in enumerate(records, start=1):
        image = record["image"]
        caption = record.get("text") or record.get("caption") or record.get("prompt") or ""

        if isinstance(image, dict):
            image = image.get("bytes")

        if isinstance(image, str):
            image_obj = Image.open(image)
        else:
            image_obj = image

        if image_obj is None:
            continue

        if getattr(image_obj, "mode", None) not in {"RGBA", "RGB", "LA", "L", "P"}:
            image_obj = image_obj.convert("RGBA")

        normalized = image_obj.convert("RGBA")
        file_name = f"{index:06d}.png"
        destination = IMAGES_DIR / file_name
        normalized.save(destination, format="PNG")

        metadata_record = {
            "file_name": f"images/{file_name}",
            "text": caption,
        }
        with metadata_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata_record, ensure_ascii=False) + "\n")

    return CLEAN_DIR
