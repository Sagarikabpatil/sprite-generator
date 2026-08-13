"""Dataset loading utilities for sprite and animation resources."""

from __future__ import annotations

from typing import Any

from datasets import load_dataset

DATASET_NAME = "Limbicnation/pixel-art-character"


def load_character_dataset() -> Any:
    """Load the Hugging Face character sprite dataset from the train split."""
    return load_dataset(DATASET_NAME, split="train")


def get_dataset_statistics(dataset: Any) -> dict[str, Any]:
    """Collect summary statistics for the loaded character dataset."""
    sample_count = len(dataset)
    widths: list[int] = []
    heights: list[int] = []
    modes: set[str] = set()
    caption_count = 0
    empty_caption_count = 0

    for sample in dataset:
        image = sample.get("image")
        caption = sample.get("text") or sample.get("caption") or sample.get("prompt") or ""

        if image is not None:
            image_size = getattr(image, "size", None)
            if image_size is not None:
                widths.append(image_size[0])
                heights.append(image_size[1])
            image_mode = getattr(image, "mode", None)
            if image_mode is not None:
                modes.add(str(image_mode))

        if isinstance(caption, str) and caption.strip():
            caption_count += 1
        else:
            empty_caption_count += 1

    return {
        "sample_count": sample_count,
        "image_dimensions": {
            "min_width": min(widths) if widths else 0,
            "max_width": max(widths) if widths else 0,
            "min_height": min(heights) if heights else 0,
            "max_height": max(heights) if heights else 0,
            "average_width": round(sum(widths) / len(widths), 2) if widths else 0,
            "average_height": round(sum(heights) / len(heights), 2) if heights else 0,
        },
        "image_modes": sorted(modes),
        "caption_availability": caption_count,
        "empty_captions": empty_caption_count,
    }
