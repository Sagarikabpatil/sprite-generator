"""Final conservative dataset curator for character sprite selection.

This module combines existing image-quality heuristics with a caption-aware filter
and the CLIP relative-margin scoring to create a conservative final curated set.
It never mutates the original datasets and is designed as a selection stage only.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.datasets.character_filter import has_reasonable_character_composition, has_sufficient_content
from app.datasets.semantic_filter import score_character_semantics

STRONG_CHARACTER_TERMS = {
    "character", "person", "human", "warrior", "knight", "wizard", "mage",
    "archer", "fighter", "soldier", "rogue", "elf", "dwarf", "princess",
    "hero", "villain", "monster", "creature", "robot", "humanoid",
    "cat", "dog", "animal", "dragon", "fairy", "skeleton", "zombie",
    "goblin", "orc", "beast", "guardian", "samurai", "ranger", "paladin",
    "cleric", "ninja", "witch", "pirate", "angel", "queen", "berserker",
    "villager", "vampire", "wolf", "lion", "bear", "unicorn", "phoenix",
    "troll", "werewolf", "ghost", "demon"
}

STRONG_NON_CHARACTER_TERMS = {
    "map", "building", "house", "furniture", "bed", "table", "chair",
    "chest", "box", "container", "weapon item", "ui", "interface",
    "menu", "icon", "tile", "tileset", "scenery", "environment",
    "landscape", "board", "inventory", "item", "object", "tool",
    "door", "prop", "props", "tree", "stone", "platform", "sign",
    "window", "vault"
}

WEAPON_TERMS = {
    "sword", "bow", "shield", "armor", "weapon", "hammer", "dagger",
    "halberd", "scythe", "wand", "spear", "claws"
}

WEAK_SUPPORTING_TERMS = {
    "game asset", "sprite asset", "pixel art asset", "transparent background",
    "indie game style", "rpg game sprite"
}

TOKEN_RE = re.compile(r"[a-zA-Z'-]+")


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.lower().replace("-", " ").split())


def caption_classification(caption: str | None) -> str:
    text = normalize_text(caption)
    if not text:
        return "missing"

    tokens = set(TOKEN_RE.findall(text))
    token_set = {token.lower() for token in tokens}

    has_strong_char = bool(token_set & STRONG_CHARACTER_TERMS)
    has_strong_non_char = bool(token_set & STRONG_NON_CHARACTER_TERMS)

    if has_strong_non_char and not has_strong_char:
        return "non_character"

    if has_strong_char:
        return "character"

    if any(term in text for term in WEAK_SUPPORTING_TERMS):
        return "ambiguous"

    # If text mentions a weapon/armor but also a character-like noun, keep it character-like.
    if token_set & WEAPON_TERMS and has_strong_char:
        return "character"

    return "ambiguous"


def classify_caption(caption: str | None) -> str:
    return caption_classification(caption)


def caption_rejection_reason(caption: str | None) -> list[str]:
    text = normalize_text(caption)
    reasons: list[str] = []
    if not text:
        return ["missing_caption"]

    token_set = set(TOKEN_RE.findall(text))
    lower_tokens = {token.lower() for token in token_set}

    has_strong_char = bool(lower_tokens & STRONG_CHARACTER_TERMS)
    has_strong_non = bool(lower_tokens & STRONG_NON_CHARACTER_TERMS)

    if has_strong_non and not has_strong_char:
        reasons.append("caption_non_character")

    if not has_strong_char and not has_strong_non and any(term in text for term in WEAK_SUPPORTING_TERMS):
        reasons.append("weak_asset_metadata")

    if any(term in text for term in ["wooden sword item", "weapon item", "item on platform", "object", "environment", "map", "building", "furniture"]) and not has_strong_char:
        reasons.append("object_or_scene_caption")

    if lower_tokens & WEAPON_TERMS and not has_strong_char:
        reasons.append("weapon_only_caption")

    return reasons if reasons else ["caption_ambiguous"]


def image_quality_ok(image: Any) -> bool:
    return has_sufficient_content(image) and has_reasonable_character_composition(image)


def final_filter(image: Any, caption: str | None, clip_details: dict[str, Any], clip_threshold: float = 0.75) -> tuple[bool, list[str], str]:
    reasons: list[str] = []

    if not image_quality_ok(image):
        reasons.append("quality_rejected")

    caption_type = classify_caption(caption)
    if caption_type == "non_character":
        reasons.append("caption_non_character")
    elif caption_type == "missing":
        reasons.append("missing_caption")
    elif caption_type == "ambiguous":
        pass

    margin = float(clip_details.get("margin", 0.0))
    character_confidence = float(clip_details.get("character_confidence", 0.0))
    non_character_confidence = float(clip_details.get("non_character_confidence", 0.0))

    if margin < clip_threshold:
        reasons.append("clip_margin_below_threshold")

    if character_confidence <= non_character_confidence:
        reasons.append("clip_not_character_preferred")

    if caption_type == "non_character":
        return False, reasons, caption_type

    if reason := caption_rejection_reason(caption):
        if caption_type != "character" and "caption_non_character" not in reasons:
            reasons.extend(reason)

    if not reasons:
        return True, [], caption_type
    return False, reasons, caption_type


def save_decision_record(filename: str, caption: str | None, clip_details: dict[str, Any], clip_threshold: float = 0.75) -> dict[str, Any]:
    image_payload = None
    accepted, reasons, caption_type = final_filter(image_payload, caption, clip_details, clip_threshold)
    return {
        "filename": filename,
        "caption": caption or "",
        "character_confidence": float(clip_details.get("character_confidence", 0.0)),
        "non_character_confidence": float(clip_details.get("non_character_confidence", 0.0)),
        "margin": float(clip_details.get("margin", 0.0)),
        "caption_classification": caption_type,
        "final_decision": accepted,
        "rejection_reasons": reasons,
    }


def create_final_dataset_record(filename: str, caption: str | None, clip_details: dict[str, Any], clip_threshold: float = 0.75) -> dict[str, Any]:
    metadata = {
        "filename": filename,
        "caption": caption or "",
        "character_confidence": float(clip_details.get("character_confidence", 0.0)),
        "non_character_confidence": float(clip_details.get("non_character_confidence", 0.0)),
        "margin": float(clip_details.get("margin", 0.0)),
    }
    return metadata
