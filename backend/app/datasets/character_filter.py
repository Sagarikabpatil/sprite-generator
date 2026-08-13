"""Heuristic character-quality filtering for the cleaned sprite dataset.

This is intentionally conservative. Simple image metrics can flag obvious junk,
while caption analysis is used to reject clearly non-character objects or scenes.
It is not a perfect semantic classifier and should be treated as a quality gate,
not a ground-truth character detector.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

CHARACTER_KEYWORDS = {
    "human",
    "person",
    "character",
    "warrior",
    "knight",
    "wizard",
    "mage",
    "archer",
    "robot",
    "animal",
    "cat",
    "dog",
    "monster",
    "creature",
    "dragon",
    "fantasy",
    "hero",
    "girl",
    "boy",
    "man",
    "woman",
    "elf",
    "orc",
    "goblin",
    "beast",
    "sprite",
    "pixel art character",
    "pixel-art character",
    "pixel art",
    "fighter",
    "ranger",
    "paladin",
    "cleric",
    "rogue",
    "mage",
    "sorcerer",
    "assassin",
    "guardian",
}

NON_CHARACTER_KEYWORDS = {
    "furniture",
    "building",
    "house",
    "map",
    "ui",
    "icon",
    "icons",
    "equipment",
    "weapon",
    "weapons",
    "item",
    "items",
    "object",
    "objects",
    "door",
    "chest",
    "tree",
    "stone",
    "terrain",
    "scenery",
    "environment",
    "background",
    "sprite sheet",
    "sprite-sheet",
    "tile",
    "tileset",
    "board",
    "game board",
    "menu",
    "hud",
    "interface",
    "armor item",
    "sword item",
    "axe item",
    "shield item",
    "bow item",
    "pack",
    "set",
    "prop",
    "props",
}


def _normalize_caption(caption: Any) -> str:
    if not isinstance(caption, str):
        return ""
    return " ".join(caption.lower().replace("-", " ").split())


def _as_rgba(image: Any) -> Image.Image:
    if image is None:
        raise ValueError("image is None")

    if isinstance(image, (str, Path)):
        with Image.open(image) as opened:
            return opened.convert("RGBA")

    if isinstance(image, bytes):
        with Image.open(io.BytesIO(image)) as opened:
            return opened.convert("RGBA")

    if isinstance(image, Image.Image):
        return image.convert("RGBA")

    raise TypeError(f"Unsupported image type: {type(image)!r}")


def _caption_mentions_character(caption: str) -> bool:
    text = _normalize_caption(caption)
    if not text:
        return False
    for term in CHARACTER_KEYWORDS:
        if term in text:
            return True
    return False


def _caption_mentions_non_character_object(caption: str) -> bool:
    text = _normalize_caption(caption)
    if not text:
        return False

    if "character" in text and any(term in text for term in {"weapon", "armor", "sword", "axe", "shield", "bow"}):
        return False

    for term in NON_CHARACTER_KEYWORDS:
        if term in text:
            return True
    return False


def has_sufficient_content(image: Any) -> bool:
    """Reject nearly blank, faint, or mostly empty imagery."""
    try:
        image_obj = _as_rgba(image)
    except (TypeError, ValueError, OSError, UnidentifiedImageError):
        return False

    array = np.asarray(image_obj)
    if array.size == 0:
        return False

    alpha = array[:, :, 3]
    rgb = array[:, :, :3]
    visible = alpha > 12
    if not np.any(visible):
        return False

    visible_fraction = float(np.mean(visible))
    if visible_fraction < 0.12:
        return False

    non_bg = rgb[visible]
    if non_bg.size == 0:
        return False

    brightness = non_bg.mean(axis=1)
    if brightness.size == 0:
        return False

    if visible_fraction < 0.25 and float(np.std(brightness)) < 10:
        return False

    return True


def has_reasonable_character_composition(image: Any) -> bool:
    """Reject obvious non-character compositions and extreme aspect ratios."""
    try:
        image_obj = _as_rgba(image)
    except (TypeError, ValueError, OSError, UnidentifiedImageError):
        return False

    array = np.asarray(image_obj)
    if array.size == 0:
        return False

    height, width = array.shape[:2]
    if width <= 0 or height <= 0:
        return False

    aspect = max(width / height, height / width)
    if aspect > 4.0:
        return False

    alpha = array[:, :, 3]
    visible = alpha > 12
    if not np.any(visible):
        return False

    ys, xs = np.where(visible)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    content_width = x1 - x0 + 1
    content_height = y1 - y0 + 1
    content_area = content_width * content_height
    total_area = width * height
    content_fraction = content_area / total_area

    if content_fraction < 0.08:
        return False
    if content_fraction > 0.9:
        return False

    if content_width < 18 or content_height < 18:
        return False

    non_bg = array[visible]
    if non_bg.size == 0:
        return False

    if float(np.std(non_bg[:, :3])) < 6 and content_fraction < 0.25:
        return False

    return True


def is_character_candidate(image: Any, caption: str | None = None) -> bool:
    """Return True when the image looks like a usable character sample, heuristically."""
    try:
        image_obj = _as_rgba(image)
    except (TypeError, ValueError, OSError, UnidentifiedImageError):
        return False

    if not has_sufficient_content(image_obj):
        return False

    if not has_reasonable_character_composition(image_obj):
        return False

    if caption is None:
        return True

    text = _normalize_caption(caption)
    if not text:
        return True

    if _caption_mentions_non_character_object(text) and not _caption_mentions_character(text):
        return False

    return True


def evaluate_character_candidate(image: Any, caption: str | None = None) -> tuple[bool, list[str]]:
    """Return the candidate verdict and a list of heuristic rejection reasons."""
    reasons: list[str] = []

    try:
        image_obj = _as_rgba(image)
    except (TypeError, ValueError, OSError, UnidentifiedImageError):
        return False, ["invalid_image"]

    if not has_sufficient_content(image_obj):
        reasons.append("blank_or_faint")
    if not has_reasonable_character_composition(image_obj):
        reasons.append("poor_composition")

    if caption is not None:
        text = _normalize_caption(caption)
        if text and _caption_mentions_non_character_object(text) and not _caption_mentions_character(text):
            reasons.append("object_or_scene_caption")

    return (not reasons), reasons
