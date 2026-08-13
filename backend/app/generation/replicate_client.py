"""Replicate-specific image generation client."""

from __future__ import annotations

import os
from pathlib import Path

import replicate
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

REPLICATE_MODEL = "black-forest-labs/flux-schnell"


def generate_image(prompt: str) -> str:
    """Generate an image from a text prompt using Replicate and return the output URL."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_token = os.getenv("REPLICATE_API_TOKEN")
    if not api_token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured in backend/.env.")

    try:
        client = replicate.Client(api_token=api_token)
        output = client.run(
            REPLICATE_MODEL,
            input={
                "prompt": prompt.strip(),
                "aspect_ratio": "1:1",
            },
        )
    except Exception as exc:
        raise RuntimeError(f"Replicate generation request failed: {exc}") from exc

    if isinstance(output, list):
        if not output:
            raise RuntimeError("Replicate returned an empty image list.")
        first_item = output[0]
        if isinstance(first_item, str):
            return first_item
        if isinstance(first_item, dict):
            for key in ("url", "image", "output"):
                if key in first_item and isinstance(first_item[key], str):
                    return first_item[key]
        raise RuntimeError("Replicate response format was unexpected.")

    if isinstance(output, dict):
        for key in ("url", "image", "output"):
            value = output.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value and isinstance(value[0], str):
                return value[0]
        raise RuntimeError("Replicate response format was unexpected.")

    if isinstance(output, str):
        return output

    raise RuntimeError("Replicate returned an unsupported output format.")
