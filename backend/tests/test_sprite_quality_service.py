from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from app.services.sprite_quality_service import (
    analyze_sprite_sheet,
    compare_sprite_frames,
)


def save_image(path: Path, size: tuple[int, int], pixels) -> Path:
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    image.save(path)
    return path


def test_analyze_sprite_sheet_reports_dimensions_and_transparency_percentages(
    tmp_path,
):
    path = save_image(
        tmp_path / "alpha-sheet.png",
        (4, 2),
        [
            (20, 30, 40, alpha)
            for alpha in (0, 0, 128, 255, 0, 255, 255, 255)
        ],
    )

    report = analyze_sprite_sheet(path)

    assert report["image_width"] == 4
    assert report["image_height"] == 2
    assert report["has_transparency"] is True
    assert report["fully_transparent_pixels"] == 3
    assert report["partially_transparent_pixels"] == 1
    assert report["opaque_pixels"] == 4
    assert report["transparent_pixel_percentage"] == 37.5
    assert report["frame_analysis"] is None


def test_analyze_sprite_sheet_supports_pathlike_individual_frame(tmp_path):
    path = save_image(
        tmp_path / "frame.png",
        (3, 2),
        [(40, 50, 60, 255)] * 6,
    )

    report = analyze_sprite_sheet(path)

    assert report["file_name"] == "frame.png"
    assert report["image_width"] == 3
    assert report["image_height"] == 2
    assert report["has_transparency"] is False
    assert report["transparent_pixel_percentage"] == 0
    assert report["warnings"] == [
        "No fully transparent pixels detected; check whether the background is intentional."
    ]


def test_analyze_sprite_sheet_rejects_missing_and_unreadable_images(tmp_path):
    with pytest.raises(FileNotFoundError):
        analyze_sprite_sheet(tmp_path / "missing.png")

    unreadable = tmp_path / "unreadable.png"
    unreadable.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="not a readable image"):
        analyze_sprite_sheet(unreadable)


@pytest.mark.parametrize(
    ("frame_width", "frame_height"),
    [(0, 2), (2, 0), (-1, 2), (2, -1)],
)
def test_analyze_sprite_sheet_rejects_nonpositive_frame_dimensions(
    tmp_path, frame_width, frame_height
):
    path = save_image(
        tmp_path / f"invalid-grid-{uuid4().hex}.png",
        (4, 4),
        [(0, 0, 0, 255)] * 16,
    )

    with pytest.raises(ValueError, match="positive integers"):
        analyze_sprite_sheet(path, frame_width, frame_height)


def test_analyze_sprite_sheet_warns_for_nondivisible_frame_grid(tmp_path):
    path = save_image(
        tmp_path / "non-divisible.png",
        (5, 3),
        [(50, 60, 70, 255)] * 15,
    )

    report = analyze_sprite_sheet(path, frame_width=2, frame_height=2)

    assert report["frame_analysis"]["columns"] == 2
    assert report["frame_analysis"]["rows"] == 1
    assert report["frame_analysis"]["frame_count"] == 2
    assert "Sprite sheet dimensions are not evenly divisible by the frame size." in report[
        "warnings"
    ]


def test_analyze_sprite_sheet_counts_fully_transparent_grid_frames(tmp_path):
    pixels = [
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (255, 0, 0, 255),
        (255, 0, 0, 255),
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        (255, 0, 0, 255),
        (255, 0, 0, 255),
    ]
    path = save_image(tmp_path / "transparent-frame.png", (4, 2), pixels)

    report = analyze_sprite_sheet(path, frame_width=2, frame_height=2)

    analysis = report["frame_analysis"]
    assert analysis["frame_count"] == 2
    assert analysis["empty_frame_count"] == 1
    assert analysis["frames"][0]["is_empty"] is True
    assert analysis["frames"][0]["content_bounds"] is None
    assert analysis["frames"][1]["is_empty"] is False
    assert "Found 1 fully transparent frame(s)." in report["warnings"]


def test_compare_sprite_frames_reports_identical_frames(tmp_path):
    pixels = [(30, 40, 50, 255)] * 4
    first = save_image(tmp_path / "first.png", (2, 2), pixels)
    second = save_image(tmp_path / "second.png", (2, 2), pixels)

    report = compare_sprite_frames([first, second])

    assert report["frame_count"] == 2
    assert report["dimensions"] == [[2, 2], [2, 2]]
    assert report["consistent_dimensions"] is True
    assert all(frame["identical_to_first_frame"] for frame in report["frames"])
    assert report["frames"][1]["mean_difference_from_first_frame"] == 0
    assert "All frames are identical; verify that animation was generated." in report[
        "warnings"
    ]


def test_compare_sprite_frames_reports_different_frames(tmp_path):
    first = save_image(
        tmp_path / "different-first.png",
        (2, 2),
        [(0, 0, 0, 255)] * 4,
    )
    second = save_image(
        tmp_path / "different-second.png",
        (2, 2),
        [(255, 255, 255, 255)] * 4,
    )

    report = compare_sprite_frames([first, second])

    assert report["consistent_dimensions"] is True
    assert report["frames"][0]["identical_to_first_frame"] is True
    assert report["frames"][1]["identical_to_first_frame"] is False
    assert report["frames"][1]["mean_difference_from_first_frame"] > 0
    assert report["warnings"] == []


def test_compare_sprite_frames_reports_inconsistent_dimensions(tmp_path):
    first = save_image(tmp_path / "small.png", (2, 2), [(0, 0, 0, 255)] * 4)
    second = save_image(tmp_path / "large.png", (3, 2), [(0, 0, 0, 255)] * 6)

    report = compare_sprite_frames([first, second])

    assert report["frame_count"] == 2
    assert report["dimensions"] == [[2, 2], [3, 2]]
    assert report["consistent_dimensions"] is False
    assert report["frames"] == []
    assert report["warnings"] == ["Frames have inconsistent dimensions."]


def test_compare_sprite_frames_rejects_missing_files_and_empty_lists(tmp_path):
    with pytest.raises(FileNotFoundError):
        compare_sprite_frames([tmp_path / "missing.png"])

    with pytest.raises(ValueError, match="At least one frame"):
        compare_sprite_frames([])


def test_quality_endpoint_accepts_owned_sheets_and_frames(isolated_client):
    client, main, folders = isolated_client
    signup = client.post(
        "/auth/signup",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "StrongPass!123",
        },
    )
    assert signup.status_code == 200
    account = signup.json()

    assets = [
        (
            "sprite_sheet",
            folders["SPRITE_SHEETS_FOLDER"] / "endpoint-sheet.png",
        ),
        ("frame", folders["GENERATED_FRAMES_FOLDER"] / "endpoint-frame.png"),
    ]
    responses = []
    for asset_type, path in assets:
        save_image(path, (2, 2), [(10, 20, 30, 255)] * 4)
        file_url = main._record_asset(account["user"]["id"], asset_type, path)
        asset_id = int(file_url.split("/")[-2])
        responses.append(
            client.get(
                f"/assets/{asset_id}/quality",
                headers={"Authorization": f"Bearer {account['token']}"},
            )
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert [response.json()["asset_type"] for response in responses] == [
        "sprite_sheet",
        "frame",
    ]
    assert all(response.json()["quality_report"]["image_width"] == 2 for response in responses)


def test_quality_endpoint_preserves_authentication_and_ownership(isolated_client):
    client, main, folders = isolated_client
    accounts = []
    for _ in range(2):
        response = client.post(
            "/auth/signup",
            json={
                "email": f"{uuid4().hex}@example.com",
                "password": "StrongPass!123",
            },
        )
        assert response.status_code == 200
        accounts.append(response.json())

    path = save_image(
        folders["SPRITE_SHEETS_FOLDER"] / "private-quality-sheet.png",
        (1, 1),
        [(10, 20, 30, 255)],
    )
    file_url = main._record_asset(accounts[0]["user"]["id"], "sprite_sheet", path)
    asset_id = int(file_url.split("/")[-2])

    assert client.get(f"/assets/{asset_id}/quality").status_code == 401
    assert client.get(
        f"/assets/{asset_id}/quality",
        headers={"Authorization": f"Bearer {accounts[1]['token']}"},
    ).status_code == 404


@pytest.mark.parametrize(
    ("path_suffix", "expected_status"),
    [("999999", 404), ("not-an-id", 422)],
)
def test_quality_endpoint_handles_invalid_asset_ids(
    isolated_client, path_suffix, expected_status
):
    client, _, _ = isolated_client
    account = client.post(
        "/auth/signup",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "StrongPass!123",
        },
    ).json()

    response = client.get(
        f"/assets/{path_suffix}/quality",
        headers={"Authorization": f"Bearer {account['token']}"},
    )

    assert response.status_code == expected_status


def test_quality_endpoint_returns_controlled_error_for_unreadable_owned_asset(
    isolated_client,
):
    client, main, folders = isolated_client
    account = client.post(
        "/auth/signup",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "StrongPass!123",
        },
    ).json()
    path = folders["SPRITE_SHEETS_FOLDER"] / "unreadable-owned-sheet.png"
    path.write_bytes(b"not an image")
    file_url = main._record_asset(account["user"]["id"], "sprite_sheet", path)
    asset_id = int(file_url.split("/")[-2])

    response = client.get(
        f"/assets/{asset_id}/quality",
        headers={"Authorization": f"Bearer {account['token']}"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The file is not a readable image."
