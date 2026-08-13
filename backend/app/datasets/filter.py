"""Safety and content filtering for the character dataset."""

from __future__ import annotations

from typing import Any

BLOCKED_TERMS = {
    "nsfw",
    "nude",
    "naked",
    "sexual",
    "explicit",
    "porn",
    "blood",
    "gore",
    "graphic violence",
    "suggestive",
}


def is_safe_caption(caption: str) -> bool:
    """Return True when the caption is safe for character LoRA training."""
    if not isinstance(caption, str):
        return False

    normalized = caption.lower().strip()
    if not normalized:
        return False

    for term in BLOCKED_TERMS:
        if term in normalized:
            return False

    return True


def filter_dataset(dataset: Any) -> Any:
    """Return a filtered dataset containing only captions that pass the safety check."""
    safe_records = []
    original_count = len(dataset)

    for sample in dataset:
        caption = sample.get("text") or sample.get("caption") or sample.get("prompt") or ""
        if is_safe_caption(caption):
            safe_records.append(sample)

    filtered_count = original_count - len(safe_records)
    print(f"Original samples: {original_count}")
    print(f"Safe samples: {len(safe_records)}")
    print(f"Filtered samples: {filtered_count}")
    return safe_records
