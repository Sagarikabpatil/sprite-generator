"""Small, reusable vocabulary layer for prompt-based character generation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCatalog:
    character_types: tuple[str, ...]
    styles: tuple[str, ...]
    viewpoints: tuple[str, ...]
    composition: tuple[str, ...]
    constraints: tuple[str, ...]
    environments: tuple[str, ...]
    weapons: tuple[str, ...]
    effects: tuple[str, ...]


PROMPT_CATALOG = PromptCatalog(
    character_types=(
        "character", "warrior", "mage", "ninja", "knight", "archer", "ranger",
        "rogue", "healer", "robot", "android", "animal", "dragon", "monster",
        "merchant", "explorer", "pilot", "inventor",
    ),
    styles=(
        "pixel art", "hand-painted pixel art", "cartoon", "anime", "chibi",
        "retro game art", "fantasy", "sci-fi", "storybook illustration",
        "comic-book art", "low-poly 3D", "flat-color illustration",
    ),
    viewpoints=("front-facing", "three-quarter view", "side view", "isometric view"),
    composition=("full body", "centered composition", "isolated character", "readable silhouette"),
    constraints=(
        "clean silhouette", "consistent proportions", "game asset",
        "transparent-background friendly", "no text or watermark",
    ),
    environments=(
        "forest", "enchanted forest", "dungeon", "castle", "village", "city",
        "space", "desert", "snow", "battlefield", "underwater", "mountain",
        "floating islands",
    ),
    weapons=("sword", "axe", "spear", "bow", "staff", "dagger", "shield", "wand", "tool"),
    effects=("fire", "smoke", "explosion", "magic", "electricity", "hit", "healing", "wind", "sparkles"),
)

PROMPT_IDEAS = [
    {"label": "Forest fox ranger", "prompt": "A pixel art fox ranger with a leaf-green cloak, small bow, and warm amber accents"},
    {"label": "Moonlit mage", "prompt": "A chibi moon mage with a star-tipped staff, lavender robes, and silver details"},
    {"label": "Clockwork inventor", "prompt": "A retro game-art clockwork inventor with brass goggles, tool belt, and teal coat"},
    {"label": "Desert knight", "prompt": "A hand-painted pixel art desert knight with layered sand-colored armor and a blue scarf"},
    {"label": "Deep-sea explorer", "prompt": "A cartoon deep-sea explorer in a compact diving suit with a glowing aqua helmet"},
    {"label": "Mushroom healer", "prompt": "A storybook mushroom healer carrying a tiny satchel and a glowing healing lantern"},
    {"label": "Frost dragon", "prompt": "A small friendly frost dragon with icy blue scales, short wings, and a bright expressive face"},
    {"label": "Space mechanic", "prompt": "A sci-fi space mechanic in a practical orange flight suit holding a compact repair tool"},
    {"label": "Castle alchemist", "prompt": "A fantasy castle alchemist with a potion belt, layered robe, and vivid green glass bottles"},
    {"label": "Mountain courier", "prompt": "A pixel art mountain courier with a red travel pack, sturdy boots, and a folded map"},
    {"label": "Neon street dancer", "prompt": "A retro arcade street dancer with a magenta jacket, cyan trim, and energetic pose"},
    {"label": "Friendly garden robot", "prompt": "A friendly little garden robot with leaf-shaped panels, round eyes, and a watering-can arm"},
]

_STYLE_RE = re.compile(
    r"\b(?:pixel\s+art|cartoon|anime|chibi|retro|fantasy|sci[- ]fi|storybook|comic-book|low-poly|flat-color)\b",
    re.IGNORECASE,
)
_ASSET_TERMS = ("game asset", "sprite", "transparent", "isolated", "full body", "character sheet")


def enrich_prompt(prompt: str) -> str:
    """Add only missing neutral asset constraints while preserving the user's wording."""
    original = prompt.strip()
    if not original:
        return original

    additions: list[str] = []
    lowered = original.lower()
    if not _STYLE_RE.search(original):
        additions.append("game-ready 2D character art")
    if not any(term in lowered for term in ("full body", "headshot", "portrait", "close-up")):
        additions.append("full body")
    if not any(term in lowered for term in ("front-facing", "three-quarter", "side view", "profile")):
        additions.append("centered composition")
    if not any(term in lowered for term in _ASSET_TERMS):
        additions.extend(("isolated character", "clean silhouette", "transparent-background friendly"))
    if "single character" not in lowered:
        additions.append("single character")
    if not any(term in lowered for term in ("no text", "no watermark")):
        additions.append("no text or watermark")

    return f"{original}, {', '.join(additions)}" if additions else original
