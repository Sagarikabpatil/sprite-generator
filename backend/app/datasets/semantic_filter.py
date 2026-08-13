"""Pretrained CLIP-style semantic filtering for character sprite selection.

This filter uses relative category confidence between broad character prompts and
non-character prompts rather than an absolute softmax score threshold. It is
intentionally conservative and designed for calibration based on real image
scores instead of fixed arbitrary cutoffs.
"""

from __future__ import annotations

from typing import Any

import torch
from PIL import Image, UnidentifiedImageError
from transformers import CLIPModel, CLIPProcessor

MODEL_NAME = "openai/clip-vit-base-patch32"
DEFAULT_CHARACTER_MIN_CONFIDENCE = 0.55
DEFAULT_CHARACTER_MARGIN = 0.05

CHARACTER_PROMPTS = [
    "a 2D game character sprite",
    "a pixel art character",
    "a full body video game character",
    "a fantasy game character",
    "a humanoid game character",
    "an animal game character",
]

NON_CHARACTER_PROMPTS = [
    "a game object",
    "a game item",
    "a game environment",
    "a game map",
    "a game UI asset",
    "a piece of furniture",
    "a building",
    "game scenery",
    "a container or chest",
    "a weapon item",
]

_MODEL: CLIPModel | None = None
_PROCESSOR: CLIPProcessor | None = None


def _load_model_and_processor() -> tuple[CLIPModel, CLIPProcessor]:
    global _MODEL, _PROCESSOR
    if _MODEL is None or _PROCESSOR is None:
        _MODEL = CLIPModel.from_pretrained(MODEL_NAME)
        _PROCESSOR = CLIPProcessor.from_pretrained(MODEL_NAME)
        _MODEL.eval()
    return _MODEL, _PROCESSOR


def _normalize_image(image: Any) -> Image.Image:
    if image is None:
        raise ValueError("image is None")
    if isinstance(image, Image.Image):
        return image.convert("RGBA")
    if isinstance(image, (bytes, bytearray)):
        from io import BytesIO

        return Image.open(BytesIO(bytes(image))).convert("RGBA")
    if isinstance(image, str):
        return Image.open(image).convert("RGBA")
    raise TypeError(f"Unsupported image type: {type(image)!r}")


def _softmax_pair(character_logit: float, non_character_logit: float) -> tuple[float, float]:
    logits = torch.tensor([character_logit, non_character_logit], dtype=torch.float32)
    probs = torch.softmax(logits, dim=0)
    return float(probs[0].item()), float(probs[1].item())


def score_character_semantics(
    image: Any,
    threshold: float | None = None,
    character_min_confidence: float = DEFAULT_CHARACTER_MIN_CONFIDENCE,
    character_margin: float = DEFAULT_CHARACTER_MARGIN,
) -> tuple[float, bool, dict[str, float]]:
    """Return a relative CLIP character score and a decision based on category margin.

    The CLIP model produces logits for every text prompt. We aggregate the logits
    for the character prompt set and the non-character prompt set, then compute a
    two-class softmax over those category logits.

    The final score is the relative character probability, not an absolute raw CLIP
    probability across all prompts. This is interpretable and robust against the
    previous issue where all prompt probabilities were near 0.10 because the model
    was normalizing across many prompts.
    """
    try:
        img = _normalize_image(image)
    except (TypeError, ValueError, OSError, UnidentifiedImageError):
        return 0.0, False, {}

    model, processor = _load_model_and_processor()
    texts = CHARACTER_PROMPTS + NON_CHARACTER_PROMPTS
    inputs = processor(text=texts, images=img, return_tensors="pt", padding=True)

    with torch.no_grad():
        logits_per_image = model(**inputs).logits_per_image[0]

    full_prompt_scores = torch.softmax(logits_per_image, dim=0)
    full_scores = {label: float(prob.item()) for label, prob in zip(texts, full_prompt_scores)}

    character_logits = logits_per_image[: len(CHARACTER_PROMPTS)]
    non_character_logits = logits_per_image[len(CHARACTER_PROMPTS) :]

    character_logit = float(character_logits.mean().item())
    non_character_logit = float(non_character_logits.mean().item())

    character_confidence, non_character_confidence = _softmax_pair(character_logit, non_character_logit)
    margin = character_confidence - non_character_confidence

    if threshold is not None:
        accepted = (character_confidence >= threshold) and (margin > 0.0)
    else:
        accepted = (
            character_confidence >= character_min_confidence
            and character_confidence > non_character_confidence
            and margin >= character_margin
        )

    result = {
        "character_confidence": character_confidence,
        "non_character_confidence": non_character_confidence,
        "margin": margin,
        "character_logit": character_logit,
        "non_character_logit": non_character_logit,
        "prompt_scores": full_scores,
    }
    return character_confidence, accepted, result


def apply_semantic_filter(
    image: Any,
    threshold: float | None = None,
    character_min_confidence: float = DEFAULT_CHARACTER_MIN_CONFIDENCE,
    character_margin: float = DEFAULT_CHARACTER_MARGIN,
) -> tuple[bool, float, dict[str, float]]:
    """Convenience wrapper returning accept/reject and relative scores."""
    score, accepted, details = score_character_semantics(
        image,
        threshold=threshold,
        character_min_confidence=character_min_confidence,
        character_margin=character_margin,
    )
    if isinstance(details, dict):
        return accepted, score, details
    return accepted, score, {"character_confidence": score}
