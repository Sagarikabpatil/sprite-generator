"""Pollinations AI image generation client."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class PollinationsTerminalError(RuntimeError):
    """A provider response that must not be retried through another endpoint."""


def _raise_if_auth_or_billing_error(status_code: int) -> None:
    if status_code in (401, 403):
        raise PollinationsTerminalError(
            "Pollinations authentication failed. Check POLLINATIONS_API_KEY."
        )
    if status_code in (402, 429):
        raise PollinationsTerminalError(
            "Pollinations request was blocked by billing or quota limits."
        )


def generate_image(prompt: str) -> tuple[bytes, str]:
    """Generate an image from a prompt using the Pollinations image API."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = (os.getenv("POLLINATIONS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "Pollinations image generation is unavailable because its API key is not configured."
        )

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
            _raise_if_auth_or_billing_error(response.status_code)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Pollinations request failed with status {response.status_code}."
                )

            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("image/"):
                return response.content, content_type

            if response.headers.get("Content-Type", "").startswith("application/json"):
                payload = response.json()
                if isinstance(payload, dict):
                    candidate = payload.get("image") or payload.get("url") or payload.get("output")
                    if isinstance(candidate, str):
                        candidate_url = urlparse(candidate)
                        if (
                            candidate_url.scheme != "https"
                            or candidate_url.hostname not in {"image.pollinations.ai", "gen.pollinations.ai"}
                            or candidate_url.username is not None
                            or candidate_url.password is not None
                            or candidate_url.port not in (None, 443)
                        ):
                            raise RuntimeError("Pollinations returned an unsupported image URL.")
                        image_response = requests.get(
                            candidate,
                            headers=headers,
                            timeout=120,
                            allow_redirects=False,
                        )
                        _raise_if_auth_or_billing_error(image_response.status_code)
                        if image_response.status_code >= 300:
                            raise RuntimeError(
                                f"Pollinations image download failed with status {image_response.status_code}."
                            )
                        image_content_type = image_response.headers.get("Content-Type", "")
                        if not image_content_type.startswith("image/"):
                            raise RuntimeError("Pollinations image download did not return image data.")
                        return image_response.content, image_content_type

            raise RuntimeError("Pollinations did not return an image payload.")
        except PollinationsTerminalError:
            raise
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise RuntimeError(f"Failed to generate image from Pollinations: {last_error}") from last_error

    raise RuntimeError("Failed to generate image from Pollinations.")
