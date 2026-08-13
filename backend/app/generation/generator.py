"""Application-level logic for generating character images from text prompts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.generation.pollinations_client import generate_image

GENERATED_FOLDER = Path(__file__).resolve().parents[1] / "generated"
GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)


def generate_character(prompt: str) -> str:
    """Generate a character image from a text prompt and save it to the app output folder."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    sanitized_prompt = prompt.strip()

    try:
        image_bytes, content_type = generate_image(sanitized_prompt)
    except (ValueError, RuntimeError) as exc:
        raise exc
    except Exception as exc:
        raise RuntimeError(f"Image generation failed: {exc}") from exc

    if not isinstance(image_bytes, (bytes, bytearray)):
        raise RuntimeError("Pollinations returned no image data.")

    extension = ".png"
    if content_type and content_type.startswith("image/"):
        extension = "." + content_type.split("/")[-1]
    elif "jpeg" in content_type.lower():
        extension = ".jpg"

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"generated_{timestamp}_{uuid4().hex[:8]}{extension}"
    file_path = GENERATED_FOLDER / filename

    try:
        file_path.write_bytes(image_bytes)
    except OSError as exc:
        raise RuntimeError(f"Failed to save generated image: {exc}") from exc

    return filename
