"""Cloudflare Workers AI image generation client."""

from __future__ import annotations

import base64
import binascii
import os

import requests

MODEL = "@cf/black-forest-labs/flux-1-schnell"
API_BASE = "https://api.cloudflare.com/client/v4/accounts"
REQUEST_TIMEOUT_SECONDS = 120


def _credentials() -> tuple[str, str]:
    account_id = (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    api_token = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    if not account_id or not api_token:
        raise RuntimeError(
            "Cloudflare Workers AI is not configured. Set CLOUDFLARE_ACCOUNT_ID "
            "and CLOUDFLARE_API_TOKEN on the backend."
        )
    return account_id, api_token


def is_enabled() -> bool:
    """Return whether an operator has explicitly opted in to Cloudflare requests."""
    return (os.getenv("CLOUDFLARE_WORKERS_AI_ENABLED") or "").strip().lower() == "true"


def is_configured_and_enabled() -> bool:
    """Check opt-in and credentials; this does not verify the account's plan or charges."""
    return is_enabled() and all(
        (os.getenv(name) or "").strip()
        for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
    )


def generate_image(prompt: str) -> tuple[bytes, str]:
    """Generate an image using FLUX.1 Schnell when explicitly enabled."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")
    if not is_enabled():
        raise RuntimeError(
            "Cloudflare Workers AI is disabled. Set CLOUDFLARE_WORKERS_AI_ENABLED=true "
            "to opt in. This setting does not verify the account plan, quota, or charges."
        )

    account_id, api_token = _credentials()
    url = f"{API_BASE}/{account_id}/ai/run/{MODEL}"
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={"prompt": prompt.strip()},
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise RuntimeError("Cloudflare Workers AI request timed out.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Cloudflare Workers AI request failed: {exc}") from exc

    if response.status_code in (401, 403):
        raise RuntimeError(
            "Cloudflare Workers AI authentication failed. Check CLOUDFLARE_API_TOKEN "
            "and its account permissions."
        )
    if response.status_code in (402, 429):
        raise RuntimeError(
            "Cloudflare Workers AI was blocked by an account quota or billing restriction. "
            "No other provider was attempted."
        )
    if response.status_code in (408, 504):
        raise RuntimeError("Cloudflare Workers AI request timed out.")
    if response.status_code >= 500:
        raise RuntimeError(
            f"Cloudflare Workers AI provider failed with status {response.status_code}."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Cloudflare Workers AI returned malformed JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Cloudflare Workers AI returned an unexpected response.")

    if response.status_code >= 400 or not payload.get("success", True):
        errors = payload.get("errors", [])
        if not isinstance(errors, list):
            errors = []
        error_text = " ".join(
            str(error.get("message", ""))
            for error in errors
            if isinstance(error, dict)
        ).lower()
        if any(
            term in error_text
            for term in (
                "quota",
                "billing",
                "neuron",
                "rate limit",
                "daily allocation",
                "limit exceeded",
                "limit reached",
                "usage limit",
            )
        ):
            raise RuntimeError(
                "Cloudflare Workers AI was blocked by an account quota or billing restriction. "
                "No other provider was attempted."
            )
        raise RuntimeError(
            f"Cloudflare Workers AI provider failed with status {response.status_code}."
        )

    result = payload.get("result")
    image = result.get("image") if isinstance(result, dict) else None
    if not isinstance(image, str) or not image:
        raise RuntimeError("Cloudflare Workers AI returned no image data.")
    try:
        image_bytes = base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("Cloudflare Workers AI returned malformed image data.") from exc
    if not image_bytes:
        raise RuntimeError("Cloudflare Workers AI returned empty image data.")

    return image_bytes, "image/jpeg"
