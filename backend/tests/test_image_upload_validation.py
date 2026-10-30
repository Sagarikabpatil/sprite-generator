from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw

from app.services import image_service, sprite_service
from app.sprite import pose_generator
from app.sprite.pose_provider import GenerationMetadata


def test_upload_service_uses_the_backend_upload_storage_root():
    from app import main

    assert image_service.UPLOAD_FOLDER.resolve() == main.UPLOAD_FOLDER.resolve()


def create_image_bytes(image_format: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (120, 80, 40)).save(buffer, format=image_format)
    return buffer.getvalue()


def mock_image_processing(monkeypatch):
    def copy_image(source: str, destination: str) -> None:
        Path(destination).write_bytes(Path(source).read_bytes())

    monkeypatch.setattr(image_service, "remove_background", copy_image)
    monkeypatch.setattr(image_service, "preprocess_character", copy_image)


@pytest.mark.parametrize(
    ("image_format", "filename", "content_type"),
    [
        ("PNG", "character.png", "image/png"),
        ("JPEG", "character.jpg", "image/jpeg"),
        ("WEBP", "character.webp", "image/webp"),
    ],
)
def test_upload_accepts_supported_decodable_image_formats(
    isolated_client, monkeypatch, image_format, filename, content_type
):
    client, _, _ = isolated_client
    token = client.post(
        "/auth/signup",
        json={"email": f"{image_format.lower()}@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    mock_image_processing(monkeypatch)

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, create_image_bytes(image_format), content_type)},
    )

    assert response.status_code == 200, response.text
    assert set(response.json()) == {"original", "removed", "processed"}
    assert len(client.get("/assets", headers={"Authorization": f"Bearer {token}"}).json()) == 3


def test_upload_rejects_non_image_bytes_and_mismatched_content_type(isolated_client):
    client, _, _ = isolated_client
    token = client.post(
        "/auth/signup",
        json={"email": "invalid-image@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    invalid_bytes = client.post(
        "/upload",
        headers=headers,
        files={"file": ("not-image.png", b"not an image", "image/png")},
    )
    invalid_type = client.post(
        "/upload",
        headers=headers,
        files={"file": ("character.png", create_image_bytes("PNG"), "text/plain")},
    )

    assert invalid_bytes.status_code == 400
    assert invalid_type.status_code == 400
    assert client.get("/assets", headers=headers).json() == []


def test_upload_rejects_images_larger_than_the_configured_limit(isolated_client):
    client, _, _ = isolated_client
    token = client.post(
        "/auth/signup",
        json={"email": "large-image@example.com", "password": "StrongPass!123"},
    ).json()["token"]

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")},
    )

    assert response.status_code == 413


def test_uploaded_original_and_processed_paths_are_recorded_and_owner_checked(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    first_token = client.post(
        "/auth/signup",
        json={"email": "upload-owner@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    other_token = client.post(
        "/auth/signup",
        json={"email": "other-upload-user@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    mock_image_processing(monkeypatch)
    content = create_image_bytes("PNG")

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {first_token}"},
        files={"file": ("character.png", content, "image/png")},
    )

    assert response.status_code == 200, response.text
    urls = response.json()
    assert set(urls) == {"original", "removed", "processed"}
    expected_paths = {
        "original": folders["UPLOAD_FOLDER"],
        "removed": folders["UPLOAD_FOLDER"],
        "processed": folders["PROCESSED_FOLDER"],
    }
    for asset_kind, url in urls.items():
        file_response = client.get(url, headers={"Authorization": f"Bearer {first_token}"})
        assert file_response.status_code == 200
        assert file_response.headers["x-asset-filename"]
        assets = client.get("/assets", headers={"Authorization": f"Bearer {first_token}"}).json()
        recorded = next(asset for asset in assets if asset["file_url"] == url)
        assert (expected_paths[asset_kind] / recorded["name"]).is_file()
        assert client.get(url, headers={"Authorization": f"Bearer {other_token}"}).status_code == 404

    assert client.get("/assets", headers={"Authorization": f"Bearer {other_token}"}).json() == []


def test_uploaded_processed_character_is_used_for_sprite_and_remains_owner_checked(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    owner = client.post(
        "/auth/signup",
        json={"email": "processed-sprite-owner@example.com", "password": "StrongPass!123"},
    ).json()
    other_user = client.post(
        "/auth/signup",
        json={"email": "processed-sprite-other@example.com", "password": "StrongPass!123"},
    ).json()
    mock_image_processing(monkeypatch)

    upload_response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {owner['token']}"},
        files={"file": ("character.png", create_image_bytes("PNG"), "image/png")},
    )

    assert upload_response.status_code == 200, upload_response.text
    assets = client.get("/assets", headers={"Authorization": f"Bearer {owner['token']}"}).json()
    processed_asset = next(asset for asset in assets if asset["asset_type"] == "processed")
    processed_path = folders["PROCESSED_FOLDER"] / processed_asset["name"]
    assert processed_path.is_file()

    video = folders["GENERATED_VIDEOS_FOLDER"] / "animation.mp4"
    video.write_bytes(b"test video")
    provider_calls = []

    class MockPoseProvider:
        last_generation = GenerationMetadata(str(video), "test report", "test prompt")

        def generate_frames(self, request, output_dir):
            provider_calls.append((Path(request.character_path).resolve(), request.action))
            frames = []
            for index in range(request.frame_count):
                frame = output_dir / f"frame_{uuid4().hex}_{index}.png"
                image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
                color = (index * 50 + 20, 240 - index * 35, 40 + index * 45, 255)
                ImageDraw.Draw(image).rectangle((0, 0, index + 1, index + 1), fill=color)
                image.save(frame)
                image.close()
                frames.append(str(frame))
            return frames

    monkeypatch.setattr(pose_generator, "FRAMES_FOLDER", folders["GENERATED_FRAMES_FOLDER"])
    monkeypatch.setattr(pose_generator, "get_pose_provider", MockPoseProvider)
    monkeypatch.setattr(sprite_service, "SHEETS_FOLDER", folders["SPRITE_SHEETS_FOLDER"])
    payload = {
        "character_path": processed_asset["file_url"],
        "action": "walk",
        "frame_count": 4,
    }
    rejected = client.post(
        "/generate-sprite",
        headers={"Authorization": f"Bearer {other_user['token']}"},
        json=payload,
    )
    assert rejected.status_code == 404
    assert provider_calls == []

    generated = client.post(
        "/generate-sprite",
        headers={"Authorization": f"Bearer {owner['token']}"},
        json=payload,
    )

    assert generated.status_code == 200, generated.text
    assert provider_calls == [(processed_path.resolve(), "walk")]
    assert len(generated.json()["frames"]) == 4
    assert generated.json()["sprite_sheet"].startswith("/assets/")
    assert generated.json()["generated_video"].startswith("/assets/")


def test_record_asset_rejects_paths_outside_trusted_storage_roots(isolated_client, tmp_path):
    _, main, _ = isolated_client
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    user_id = main._create_user_record("outside-check@example.com", "StrongPass!123")["id"]

    with pytest.raises(ValueError, match="outside its expected storage directory"):
        main._record_asset(user_id, "upload", outside)


def test_failed_asset_recording_rolls_back_and_removes_only_new_upload_files(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    token = client.post(
        "/auth/signup",
        json={"email": "recording-failure@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    mock_image_processing(monkeypatch)

    def fail_recording(*args, **kwargs):
        raise ValueError("recording failed")

    monkeypatch.setattr(main, "_record_assets", fail_recording)
    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("character.png", create_image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 500
    assert "new upload files were removed" in response.json()["detail"]
    assert client.get("/assets", headers={"Authorization": f"Bearer {token}"}).json() == []
    assert list(folders["UPLOAD_FOLDER"].iterdir()) == []
    assert list(folders["PROCESSED_FOLDER"].iterdir()) == []


def test_upload_reports_preprocessing_failure_without_recording_assets(isolated_client, monkeypatch):
    client, _, _ = isolated_client
    token = client.post(
        "/auth/signup",
        json={"email": "preprocess-failure@example.com", "password": "StrongPass!123"},
    ).json()["token"]
    monkeypatch.setattr(
        image_service,
        "remove_background",
        lambda source, destination: (_ for _ in ()).throw(RuntimeError("provider failure")),
    )

    response = client.post(
        "/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("character.png", create_image_bytes("PNG"), "image/png")},
    )

    assert response.status_code == 422
    assert "could not be processed" in response.json()["detail"].lower()
    assert client.get("/assets", headers={"Authorization": f"Bearer {token}"}).json() == []
