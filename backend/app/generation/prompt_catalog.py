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
    character_types=("character", "warrior", "mage", "ninja", "knight", "archer", "robot", "animal", "monster"),
    styles=("pixel art", "cartoon", "anime", "chibi", "retro", "fantasy", "sci-fi", "realistic"),
    viewpoints=("front-facing", "three-quarter view", "side view"),
    composition=("full body", "centered composition", "isolated character"),
    constraints=("clean silhouette", "consistent proportions", "game asset", "transparent-background friendly"),
    environments=("forest", "dungeon", "castle", "village", "city", "space", "desert", "snow", "battlefield"),
    weapons=("sword", "axe", "spear", "bow", "staff", "dagger", "gun"),
    effects=("fire", "smoke", "explosion", "magic", "electricity", "hit", "healing"),
)

_STYLE_RE = re.compile(r"\b(?:pixel\s+art|cartoon|anime|chibi|retro|fantasy|sci[- ]fi|realistic)\b", re.IGNORECASE)
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

    return f"{original}, {', '.join(additions)}" if additions else original
