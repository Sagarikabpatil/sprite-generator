"""Pollinations AI image generation client."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def generate_image(prompt: str) -> tuple[bytes, str]:
    """Generate an image from a prompt using the Pollinations image API."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = (os.getenv("POLLINATIONS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("POLLINATIONS_API_KEY is not configured in backend/.env.")

    sanitized_prompt = prompt.strip()
    encoded_prompt = quote(sanitized_prompt)
    image_urls = [
        f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux",
        f"https://gen.pollinations.ai/image/{encoded_prompt}?model=flux",
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*, application/json",
    }

    last_error: Exception | None = None

    for url in image_urls:
        try:
            response = requests.get(url, headers=headers, timeout=120)

            if response.status_code == 401:
                raise RuntimeError("Pollinations authentication failed. Check POLLINATIONS_API_KEY.")
            if response.status_code == 402:
                raise RuntimeError("Pollinations request failed: insufficient credits or payment required.")
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Pollinations request failed with status {response.status_code}: {response.text[:200]}"
                )

            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                return response.content, content_type

            if response.headers.get("Content-Type", "").startswith("application/json"):
                payload = response.json()
                if isinstance(payload, dict):
                    candidate = payload.get("image") or payload.get("url") or payload.get("output")
                    if isinstance(candidate, str):
                        return requests.get(candidate, headers=headers, timeout=120).content, "image/png"

            raise RuntimeError("Pollinations did not return an image payload.")
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise RuntimeError(f"Failed to generate image from Pollinations: {last_error}") from last_error

    raise RuntimeError("Failed to generate image from Pollinations.")
