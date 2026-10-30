import base64
from io import BytesIO
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from app.generation import cloudflare_client, generator


def create_user(client, email=None):
    email = email or f"{uuid4().hex}@example.com"
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "StrongPass!123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("get", "/history", {}),
        ("get", "/assets", {}),
        ("post", "/upload", {"files": {"file": ("image.png", b"image", "image/png")}}),
        ("post", "/generate", {"json": {"prompt": "warrior"}}),
        (
            "post",
            "/generate-sprite",
            {"json": {"character_path": "/assets/1/file", "action": "walk", "frame_count": 4}},
        ),
        (
            "post",
            "/generate-sprite-from-prompt",
            {"json": {"prompt": "warrior", "action": "walk", "frame_count": 4}},
        ),
    ],
)
def test_protected_endpoints_reject_missing_and_invalid_tokens(
    isolated_client, method, path, kwargs
):
    client, _, _ = isolated_client
    request = getattr(client, method)
    assert request(path, **kwargs).status_code == 401
    assert request(path, headers=auth("invalid-token"), **kwargs).status_code == 401


def test_expired_token_is_rejected(isolated_client):
    client, main, _ = isolated_client
    account = create_user(client)
    expired_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with main.get_db_connection() as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ? WHERE token = ?",
            (expired_at, account["token"]),
        )

    assert client.get("/history", headers=auth(account["token"])).status_code == 401


def test_logout_invalidates_session(isolated_client):
    client, _, _ = isolated_client
    account = create_user(client)

    response = client.post("/auth/logout", headers=auth(account["token"]))

    assert response.status_code == 204
    assert client.get("/auth/me", headers=auth(account["token"])).status_code == 401


def test_history_assets_and_files_are_isolated_between_users(isolated_client):
    client, main, folders = isolated_client
    first_user = create_user(client)
    second_user = create_user(client)
    image_path = folders["GENERATED_FOLDER"] / "first-user.png"
    image_path.write_bytes(b"private image")
    first_file_url = main._record_asset(first_user["user"]["id"], "character", image_path)
    main._record_generation(
        first_user["user"]["id"],
        "first user's prompt",
        "character",
        "completed",
        character_path=first_file_url,
    )
    asset_id = int(first_file_url.split("/")[-2])

    first_history = client.get("/history", headers=auth(first_user["token"]))
    first_assets = client.get("/assets", headers=auth(first_user["token"]))
    second_history = client.get("/history", headers=auth(second_user["token"]))
    second_assets = client.get("/assets", headers=auth(second_user["token"]))

    assert len(first_history.json()) == 1
    assert first_history.json()[0]["character_path"] == first_file_url
    assert len(first_assets.json()) == 1
    assert first_assets.json()[0]["file_url"] == first_file_url
    assert second_history.json() == []
    assert second_assets.json() == []
    assert client.get(first_file_url, headers=auth(second_user["token"])).status_code == 404
    assert client.delete(f"/assets/{asset_id}", headers=auth(second_user["token"])).status_code == 404
    assert image_path.read_bytes() == b"private image"


def test_owner_can_delete_their_own_asset(isolated_client):
    client, main, folders = isolated_client
    account = create_user(client)
    image_path = folders["GENERATED_FOLDER"] / "deletable.png"
    image_path.write_bytes(b"owned")
    file_url = main._record_asset(account["user"]["id"], "character", image_path)
    asset_id = int(file_url.split("/")[-2])

    response = client.delete(f"/assets/{asset_id}", headers=auth(account["token"]))

    assert response.status_code == 204
    assert not image_path.exists()
    assert client.get(file_url, headers=auth(account["token"])).status_code == 404


def test_successful_generation_records_owned_asset_and_history(isolated_client, monkeypatch):
    client, main, folders = isolated_client
    account = create_user(client)
    generated = folders["GENERATED_FOLDER"] / "character-result.png"

    def generate(_prompt):
        generated.write_bytes(b"generated image")
        return generated.name

    monkeypatch.setattr(main, "generate_character", generate)
    response = client.post(
        "/generate",
        json={"prompt": "pixel art warrior"},
        headers=auth(account["token"]),
    )

    assert response.status_code == 200, response.text
    asset_url = response.json()["image"]
    assert asset_url.startswith("/assets/")
    downloaded = client.get(asset_url, headers=auth(account["token"]))
    assert downloaded.content == b"generated image"
    assert downloaded.headers["x-asset-filename"].endswith(".png")
    assert "attachment" in downloaded.headers["content-disposition"]
    assert client.get("/assets", headers=auth(account["token"])).json()[0]["file_url"] == asset_url
    history = client.get("/history", headers=auth(account["token"])).json()
    assert history[0]["character_path"] == asset_url


def test_cloudflare_generation_preserves_auth_asset_ownership_and_history(
    isolated_client, monkeypatch
):
    client, _, folders = isolated_client
    monkeypatch.setattr(generator, "GENERATED_FOLDER", folders["GENERATED_FOLDER"])
    account = create_user(client)
    mock_cloudflare_token = "test-cloudflare-token-not-for-api-response"
    image_buffer = BytesIO()
    Image.new("RGB", (10, 10), (40, 100, 160)).save(image_buffer, format="PNG")
    image_payload = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    provider_calls = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"success": True, "result": {"image": image_payload}}

    def fake_post(url, **kwargs):
        provider_calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account-test")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", mock_cloudflare_token)
    monkeypatch.setenv("CLOUDFLARE_WORKERS_AI_ENABLED", "true")
    monkeypatch.setattr(cloudflare_client.requests, "post", fake_post)

    unauthenticated = client.post(
        "/generate",
        json={"prompt": "blue sprite", "provider": "cloudflare"},
    )
    assert unauthenticated.status_code == 401
    assert provider_calls == []

    response = client.post(
        "/generate",
        json={"prompt": "blue sprite", "provider": "cloudflare"},
        headers=auth(account["token"]),
    )

    assert response.status_code == 200, response.text
    assert mock_cloudflare_token not in response.text
    image_url = response.json()["image"]
    assert client.get(image_url, headers=auth(account["token"])).status_code == 200
    assert len(client.get("/assets", headers=auth(account["token"])).json()) == 1
    history = client.get("/history", headers=auth(account["token"])).json()
    assert len(history) == 1
    assert history[0]["character_path"] == image_url
    another_user = create_user(client)
    assert client.get("/history", headers=auth(another_user["token"])).json() == []
    assert client.get(image_url, headers=auth(another_user["token"])).status_code == 404


def test_sprite_generation_records_owned_video_frames_and_sheet(isolated_client, monkeypatch):
    client, main, folders = isolated_client
    account = create_user(client)
    character = folders["PROCESSED_FOLDER"] / "character.png"
    frame = folders["GENERATED_FRAMES_FOLDER"] / "frame_000.png"
    sheet = folders["SPRITE_SHEETS_FOLDER"] / "sheet.png"
    video = folders["GENERATED_VIDEOS_FOLDER"] / "animation.mp4"
    for path in (character, frame, sheet, video):
        path.write_bytes(b"test asset")
    character_url = main._record_asset(account["user"]["id"], "processed", character)
    monkeypatch.setattr(
        main,
        "generate_sprite",
        lambda character_path, action, frame_count: {
            "action": action,
            "frame_count": frame_count,
            "frames": [str(frame)],
            "sprite_sheet": str(sheet),
            "generated_video": str(video),
            "provider": "test provider",
        },
    )

    response = client.post(
        "/generate-sprite",
        headers=auth(account["token"]),
        json={"character_path": character_url, "action": "walk", "frame_count": 4},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["generated_video"].startswith("/assets/")
    assert result["action_label"] == "Walk"
    assert result["frames"][0].startswith("/assets/")
    assert result["sprite_sheet"].startswith("/assets/")
    downloaded_video = client.get(result["generated_video"], headers=auth(account["token"]))
    assert downloaded_video.content == b"test asset"
    assert downloaded_video.headers["content-type"] == "video/mp4"
    history = client.get("/history", headers=auth(account["token"])).json()
    assert history[0]["video_path"] == result["generated_video"]
    assert history[0]["sprite_sheet_path"] == result["sprite_sheet"]


def test_failed_generation_does_not_record_successful_asset_or_history(
    isolated_client, monkeypatch
):
    client, main, _ = isolated_client
    account = create_user(client)

    def fail_generation(_prompt):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(main, "generate_character", fail_generation)
    response = client.post(
        "/generate",
        json={"prompt": "pixel art warrior"},
        headers=auth(account["token"]),
    )

    assert response.status_code == 500
    assert client.get("/assets", headers=auth(account["token"])).json() == []
    assert client.get("/history", headers=auth(account["token"])).json() == []


def test_failed_animation_does_not_record_output_assets_or_history(isolated_client, monkeypatch):
    client, main, folders = isolated_client
    account = create_user(client)
    character = folders["PROCESSED_FOLDER"] / "source.png"
    character.write_bytes(b"source")
    character_url = main._record_asset(account["user"]["id"], "processed", character)

    def fail_generation(*_args):
        raise main.PoseProviderError("provider unavailable")

    monkeypatch.setattr(main, "generate_sprite", fail_generation)
    response = client.post(
        "/generate-sprite",
        headers=auth(account["token"]),
        json={"character_path": character_url, "action": "walk", "frame_count": 4},
    )

    assert response.status_code == 502
    assert len(client.get("/assets", headers=auth(account["token"])).json()) == 1
    assert client.get("/history", headers=auth(account["token"])).json() == []


@pytest.mark.parametrize(
    ("character_path", "expected_status"),
    [
        ("", 400),
        ("/processed/private.png", 400),
        ("/assets/999999/file", 404),
    ],
)
def test_sprite_generation_rejects_missing_or_invalid_asset_before_provider(
    isolated_client, monkeypatch, character_path, expected_status
):
    client, main, _ = isolated_client
    account = create_user(client)
    provider_calls = []
    monkeypatch.setattr(
        main,
        "generate_sprite",
        lambda *args: provider_calls.append(args),
    )

    response = client.post(
        "/generate-sprite",
        headers=auth(account["token"]),
        json={"character_path": character_path, "action": "walk", "frame_count": 4},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]
    assert provider_calls == []


def test_upload_records_original_and_processed_files_for_authenticated_user(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    account = create_user(client)

    def fake_process(_file, *, filename):
        original = folders["UPLOAD_FOLDER"] / filename
        removed = folders["UPLOAD_FOLDER"] / f"no_bg_{filename}.png"
        processed = folders["PROCESSED_FOLDER"] / f"processed_{filename}.png"
        original.write_bytes(b"original")
        removed.write_bytes(b"removed")
        processed.write_bytes(b"processed")
        return {
            "original_path": original,
            "removed_path": removed,
            "processed_path": processed,
        }

    monkeypatch.setattr(main, "process_uploaded_image", fake_process)
    response = client.post(
        "/upload",
        headers=auth(account["token"]),
        files={"file": ("../unsafe.png", b"image", "image/png")},
    )

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"original", "removed", "processed"}
    assert len(client.get("/assets", headers=auth(account["token"])).json()) == 3
    for url in response.json().values():
        assert client.get(url, headers=auth(account["token"])).status_code == 200


def test_asset_filename_traversal_is_rejected(isolated_client):
    client, main, _ = isolated_client
    account = create_user(client)
    with main.get_db_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO user_assets (user_id, asset_type, name, file_url) VALUES (?, ?, ?, ?)",
            (account["user"]["id"], "character", "..\\outside.png", "/assets/1/file"),
        )

    response = client.get(
        f"/assets/{cursor.lastrowid}/file",
        headers=auth(account["token"]),
    )

    assert response.status_code == 404
