"""Application-level logic for generating character images from text prompts."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.generation import cloudflare_client
from app.generation.pollinations_client import PollinationsTerminalError, generate_image
from app.generation.prompt_catalog import enrich_prompt

ImageProviderName = Literal["pollinations", "cloudflare"]
IMAGE_PROVIDERS = frozenset({"pollinations", "cloudflare"})
GENERATED_FOLDER = Path(__file__).resolve().parents[1] / "generated"
GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)


def _resolve_provider(provider: str | None) -> str:
    selected = (
        os.getenv("ASSETAI_IMAGE_PROVIDER", "pollinations")
        if provider is None
        else provider
    ).strip().lower()
    if selected not in IMAGE_PROVIDERS:
        raise RuntimeError(
            "Unsupported image provider. Choose one of: pollinations, cloudflare."
        )
    return selected


def _request_image(prompt: str, provider: str) -> tuple[bytes, str]:
    if provider == "cloudflare":
        return cloudflare_client.generate_image(prompt)
    return generate_image(prompt)


def generate_character(
    prompt: str,
    provider: ImageProviderName | None = None,
    allow_cloudflare_fallback: bool | None = None,
) -> str:
    """Generate a character image from a text prompt and save it to the app output folder."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    sanitized_prompt = enrich_prompt(prompt)
    selected_provider = _resolve_provider(provider)

    try:
        image_bytes, content_type = _request_image(sanitized_prompt, selected_provider)
    except PollinationsTerminalError:
        raise
    except Exception as exc:
        if (
            selected_provider != "pollinations"
            or allow_cloudflare_fallback is False
            or not cloudflare_client.is_configured_and_enabled()
        ):
            if isinstance(exc, (ValueError, RuntimeError)):
                raise
            raise RuntimeError(f"Image generation failed: {exc}") from exc
        try:
            image_bytes, content_type = _request_image(sanitized_prompt, "cloudflare")
            selected_provider = "cloudflare"
        except Exception as fallback_error:
            raise RuntimeError(
                f"The pollinations image provider failed and Cloudflare Workers AI "
                f"could not provide an image: {fallback_error}"
            ) from fallback_error

    if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
        raise RuntimeError(f"{selected_provider.title()} returned no image data.")
    if not content_type.lower().startswith("image/"):
        raise RuntimeError(f"{selected_provider.title()} returned a non-image response.")

    format_extensions = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError, ValueError) as exc:
        raise RuntimeError(f"{selected_provider.title()} returned invalid image data.") from exc
    if image_format not in format_extensions or width < 1 or height < 1 or width * height > 40_000_000:
        raise RuntimeError(f"{selected_provider.title()} returned an unsupported or oversized image.")

    extension = format_extensions[image_format]

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_{timestamp}_{uuid4().hex[:8]}{extension}"
    file_path = GENERATED_FOLDER / filename

    try:
        file_path.write_bytes(image_bytes)
    except OSError as exc:
        raise RuntimeError(f"Failed to save generated image: {exc}") from exc

    return filename
