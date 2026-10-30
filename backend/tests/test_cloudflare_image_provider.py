import base64
from io import BytesIO

import pytest
import requests
from PIL import Image

from app.generation import cloudflare_client, generator, pollinations_client


def create_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (20, 90, 180)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def configure_cloudflare(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-test")
    monkeypatch.setenv("CLOUDFLARE_WORKERS_AI_ENABLED", "true")


def test_cloudflare_decodes_image_response_and_keeps_credentials_server_side(monkeypatch):
    configure_cloudflare(monkeypatch)
    image_bytes = create_png()
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(
            200,
            {"success": True, "result": {"image": base64.b64encode(image_bytes).decode("ascii")}},
        )

    monkeypatch.setattr(cloudflare_client.requests, "post", fake_post)

    result = cloudflare_client.generate_image("sprite character")

    assert result == (image_bytes, "image/jpeg")
    assert calls[0][0] == (
        "https://api.cloudflare.com/client/v4/accounts/account-test/ai/run/"
        "@cf/black-forest-labs/flux-1-schnell"
    )
    assert calls[0][1]["headers"]["Authorization"] == "Bearer token-test"
    assert calls[0][1]["json"] == {"prompt": "sprite character"}
    assert calls[0][1]["allow_redirects"] is False


def test_cloudflare_disabled_guard_makes_no_request_without_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-test")
    monkeypatch.delenv("CLOUDFLARE_WORKERS_AI_ENABLED", raising=False)
    calls = []
    monkeypatch.setattr(cloudflare_client.requests, "post", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(RuntimeError, match="disabled"):
        cloudflare_client.generate_image("sprite character")

    assert calls == []


@pytest.mark.parametrize(
    "status_code, message",
    [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (402, "quota"),
        (429, "quota"),
        (408, "timed out"),
        (504, "timed out"),
        (503, "provider failed"),
    ],
)
def test_cloudflare_reports_auth_quota_and_provider_failures(
    monkeypatch, status_code, message
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(
        cloudflare_client.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code, {"success": False, "errors": []}),
    )

    with pytest.raises(RuntimeError, match=message):
        cloudflare_client.generate_image("sprite character")


def test_cloudflare_reports_timeout(monkeypatch):
    configure_cloudflare(monkeypatch)

    def timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(cloudflare_client.requests, "post", timeout)

    with pytest.raises(RuntimeError, match="timed out"):
        cloudflare_client.generate_image("sprite character")


def test_cloudflare_reports_malformed_json(monkeypatch):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(
        cloudflare_client.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(200, ValueError("invalid json")),
    )

    with pytest.raises(RuntimeError, match="malformed JSON"):
        cloudflare_client.generate_image("sprite character")


@pytest.mark.parametrize(
    "payload",
    [
        {"success": True, "result": {"image": "not-base64"}},
        {"success": True, "result": {"image": ""}},
        {"success": True, "result": {}},
        [],
    ],
)
def test_cloudflare_rejects_malformed_image_responses(monkeypatch, payload):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(
        cloudflare_client.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(200, payload),
    )

    with pytest.raises(RuntimeError, match="image|response"):
        cloudflare_client.generate_image("sprite character")


def test_ordinary_pollinations_failure_falls_back_to_explicitly_enabled_cloudflare(
    monkeypatch, tmp_path
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    cloudflare_calls = []
    monkeypatch.setattr(
        generator,
        "generate_image",
        lambda _prompt: (_ for _ in ()).throw(RuntimeError("primary unavailable")),
    )
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda prompt: cloudflare_calls.append(prompt) or (create_png(), "image/jpeg"),
    )

    filename = generator.generate_character("sprite character", "pollinations")

    assert (tmp_path / filename).is_file()
    assert len(cloudflare_calls) == 1
    with Image.open(tmp_path / filename) as image:
        assert image.size == (8, 8)


def test_explicitly_disabled_fallback_does_not_call_cloudflare(monkeypatch, tmp_path):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(
        generator,
        "generate_image",
        lambda _prompt: (_ for _ in ()).throw(RuntimeError("primary unavailable")),
    )
    cloudflare_calls = []
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda *args: cloudflare_calls.append(args),
    )

    with pytest.raises(RuntimeError, match="primary unavailable"):
        generator.generate_character(
            "sprite character",
            "pollinations",
            allow_cloudflare_fallback=False,
        )

    assert cloudflare_calls == []


def test_pollinations_http_5xx_falls_back_to_explicitly_enabled_cloudflare(
    monkeypatch, tmp_path
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-only-pollinations-key")
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    pollinations_calls = []
    cloudflare_calls = []

    class ProviderResponse:
        status_code = 503
        headers = {}

    monkeypatch.setattr(
        pollinations_client.requests,
        "get",
        lambda url, **kwargs: pollinations_calls.append(url) or ProviderResponse(),
    )
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda prompt: cloudflare_calls.append(prompt) or (create_png(), "image/jpeg"),
    )

    filename = generator.generate_character("sprite character", "pollinations")

    assert (tmp_path / filename).is_file()
    assert len(pollinations_calls) == 2
    assert cloudflare_calls


def test_character_generation_does_not_fallback_without_cloudflare_opt_in(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_WORKERS_AI_ENABLED", raising=False)
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(
        generator,
        "generate_image",
        lambda _prompt: (_ for _ in ()).throw(RuntimeError("primary unavailable")),
    )
    fallback_calls = []
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda *args: fallback_calls.append(args),
    )

    with pytest.raises(RuntimeError, match="primary unavailable"):
        generator.generate_character("sprite character", "pollinations")

    assert fallback_calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "status_code, expected_message",
    [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (402, "quota or billing"),
        (429, "quota or billing"),
        (503, "provider failed"),
    ],
)
def test_cloudflare_auth_and_quota_failures_never_fall_back_to_pollinations(
    monkeypatch, tmp_path, status_code, expected_message
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(generator, "generate_image", lambda *args: pytest.fail("Pollinations called"))
    monkeypatch.setattr(
        cloudflare_client.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code, {"success": False, "errors": []}),
    )

    with pytest.raises(RuntimeError, match=expected_message):
        generator.generate_character("sprite character", "cloudflare")


@pytest.mark.parametrize("status_code", [401, 402, 403, 429])
def test_pollinations_auth_and_quota_responses_never_fall_back_to_cloudflare(
    monkeypatch, tmp_path, status_code
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-only")
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    cloudflare_calls = []

    class ProviderResponse:
        headers = {}

        def __init__(self, response_status):
            self.status_code = response_status

    monkeypatch.setattr(
        pollinations_client.requests,
        "get",
        lambda *args, **kwargs: ProviderResponse(status_code),
    )
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda *args: cloudflare_calls.append(args),
    )

    with pytest.raises(RuntimeError, match="authentication failed|billing or quota"):
        generator.generate_character("sprite character", "pollinations")

    assert cloudflare_calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("status_code", [401, 402, 429])
def test_pollinations_auth_and_quota_errors_on_download_never_fall_back_to_cloudflare(
    monkeypatch, tmp_path, status_code
):
    configure_cloudflare(monkeypatch)
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-only-pollinations-key")
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    pollinations_calls = []
    cloudflare_calls = []

    class JsonResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        @staticmethod
        def json():
            return {"url": "https://image.pollinations.ai/generated.png"}

    class DownloadResponse:
        headers = {}

        def __init__(self, response_status):
            self.status_code = response_status

    def fake_get(url, **kwargs):
        pollinations_calls.append(url)
        if len(pollinations_calls) == 1:
            return JsonResponse()
        return DownloadResponse(status_code)

    monkeypatch.setattr(pollinations_client.requests, "get", fake_get)
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda *args: cloudflare_calls.append(args),
    )

    with pytest.raises(RuntimeError, match="authentication failed|billing or quota"):
        generator.generate_character("sprite character", "pollinations")

    assert len(pollinations_calls) == 2
    assert cloudflare_calls == []
    assert list(tmp_path.iterdir()) == []


def test_invalid_configured_provider_is_rejected_without_provider_calls(monkeypatch):
    monkeypatch.setenv("ASSETAI_IMAGE_PROVIDER", "unknown")
    provider_calls = []
    monkeypatch.setattr(generator, "generate_image", lambda *args: provider_calls.append(args))
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda *args: provider_calls.append(args),
    )

    with pytest.raises(RuntimeError, match="Unsupported image provider"):
        generator.generate_character("sprite character")

    assert provider_calls == []


def test_cloudflare_bytes_are_validated_before_they_are_saved(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDFLARE_WORKERS_AI_ENABLED", "true")
    monkeypatch.setattr(generator, "GENERATED_FOLDER", tmp_path)
    monkeypatch.setattr(
        cloudflare_client,
        "generate_image",
        lambda _prompt: (b"not an image", "image/jpeg"),
    )

    with pytest.raises(RuntimeError, match="Cloudflare returned invalid image data"):
        generator.generate_character("sprite character", "cloudflare")

    assert list(tmp_path.iterdir()) == []
