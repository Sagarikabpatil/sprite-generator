"""Thin orchestration for prompt-to-character-to-sprite generation."""

from __future__ import annotations

from app.generation.generator import GENERATED_FOLDER, ImageProviderName, generate_character
from app.services.image_service import process_image_path
from app.services.sprite_service import generate_sprite


def generate_sprite_from_prompt(
    prompt: str,
    action: str,
    frame_count: int,
    provider: ImageProviderName | None = None,
    allow_cloudflare_fallback: bool | None = None,
) -> dict[str, object]:
    """Generate, preprocess, and animate a character without making an HTTP hop."""
    if provider is not None or allow_cloudflare_fallback is not None:
        generated_filename = generate_character(
            prompt,
            provider,
            allow_cloudflare_fallback,
        )
    else:
        generated_filename = generate_character(prompt)
    generated_path = GENERATED_FOLDER / generated_filename
    processed = process_image_path(generated_path, generated_filename)
    sprite = generate_sprite(str(processed["processed_path"]), action, frame_count)

    return {
        **sprite,
        "prompt": prompt,
        "generated_character_path": generated_path,
        "generated_character_url": f"http://127.0.0.1:8000/generated/{generated_filename}",
        "processed_character_path": processed["processed_path"],
        "processed_character_url": processed["processed_url"],
        "action": action,
        "frame_count": frame_count,
    }
