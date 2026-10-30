from io import BytesIO

import pytest
from PIL import Image

from app.generation import generator, pollinations_client
from app.generation.pollinations_client import generate_image


def create_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (12, 12), (220, 30, 80, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_pollinations_requires_a_configured_key_instead_of_returning_placeholder(monkeypatch):
    monkeypatch.delenv("POLLINATIONS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="not configured"):
        generate_image("a pixel art ranger")


def test_character_generation_validates_and_saves_real_image_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(generator, "generate_image", lambda prompt: (create_png(), "image/png"))

    filename = generator.generate_character("a friendly robot")

    assert filename.endswith(".png")
    assert (tmp_path / filename).is_file()
    with Image.open(tmp_path / filename) as image:
        assert image.size == (12, 12)


def test_character_generation_rejects_invalid_provider_output_without_saving(monkeypatch, tmp_path):
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(generator, "generate_image", lambda prompt: (b"not an image", "image/png"))

    with pytest.raises(RuntimeError, match="invalid image data"):
        generator.generate_character("a friendly robot")

    assert list(tmp_path.iterdir()) == []


def test_missing_pollinations_configuration_does_not_record_successful_generation(
    isolated_client, monkeypatch
):
    client, _, _ = isolated_client
    monkeypatch.delenv("POLLINATIONS_API_KEY", raising=False)
    token = client.post(
        "/auth/signup",
        json={"email": "no-provider-key@example.com", "password": "StrongPass!123"},
    ).json()["token"]

    response = client.post(
        "/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": "a friendly robot"},
    )

    assert response.status_code == 500
    assert "not configured" in response.json()["detail"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/assets", headers=headers).json() == []
    assert client.get("/history", headers=headers).json() == []


def test_pollinations_does_not_fetch_untrusted_image_urls(monkeypatch):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-only")
    requests_made = []

    class JsonResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        @staticmethod
        def json():
            return {"url": "http://127.0.0.1/private-image"}

    def fake_get(url, **kwargs):
        requests_made.append(url)
        return JsonResponse()

    monkeypatch.setattr(pollinations_client.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="unsupported image URL"):
        pollinations_client.generate_image("a pixel art ranger")

    assert len(requests_made) == 2
    assert all(url.startswith("https://") for url in requests_made)


def test_pollinations_does_not_retry_alternate_endpoint_after_quota_response(monkeypatch):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-only")
    requests_made = []

    class QuotaResponse:
        status_code = 402
        headers = {}

    def fake_get(url, **kwargs):
        requests_made.append(url)
        return QuotaResponse()

    monkeypatch.setattr(pollinations_client.requests, "get", fake_get)

    with pytest.raises(RuntimeError, match="billing or quota"):
        pollinations_client.generate_image("a pixel art ranger")

    assert len(requests_made) == 1
