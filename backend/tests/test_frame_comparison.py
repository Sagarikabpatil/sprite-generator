import json
from pathlib import Path
from uuid import uuid4

from PIL import Image


def create_user(client):
    response = client.post(
        "/auth/signup",
        json={
            "email": f"{uuid4().hex}@example.com",
            "password": "StrongPass!123",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def write_frame(path: Path, color):
    Image.new("RGBA", (8, 8), color).save(path)
    return path


def seed_sheet(client, main, folders, user, *, frame_count=2):
    frame_paths = [
        write_frame(
            folders["GENERATED_FRAMES_FOLDER"] / f"comparison-{uuid4().hex}-{index}.png",
            (255, 0, 0, 255) if index == 0 else (0, 255, 0, 255),
        )
        for index in range(frame_count)
    ]
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"comparison-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    frame_urls = [
        main._record_asset(user["user"]["id"], "frame", path)
        for path in frame_paths
    ]
    sheet_url = main._record_asset(user["user"]["id"], "sprite_sheet", sheet_path)
    frame_ids = [int(url.split("/")[-2]) for url in frame_urls]
    main._record_generation(
        user["user"]["id"],
        "walk",
        "walk",
        "completed",
        sprite_sheet_path=sheet_url,
        frame_asset_ids=frame_ids,
    )
    return sheet_url, frame_ids


def test_frame_comparison_uses_saved_exact_frame_association(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_url, expected_frame_ids = seed_sheet(client, main, folders, user)
    sheet_id = int(sheet_url.split("/")[-2])

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["asset_id"] == sheet_id
    assert result["frame_comparison"]["frame_count"] == len(expected_frame_ids)
    assert result["frame_comparison"]["consistent_dimensions"] is True
    assert [frame["index"] for frame in result["frame_comparison"]["frames"]] == [0, 1]


def test_frame_comparison_returns_not_found_for_sheet_without_association(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"legacy-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    sheet_url = main._record_asset(user["user"]["id"], "sprite_sheet", sheet_path)
    sheet_id = int(sheet_url.split("/")[-2])

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 404
    assert "association" in response.json()["detail"]


def test_frame_comparison_rejects_non_sprite_sheet_asset(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    frame_path = write_frame(
        folders["GENERATED_FRAMES_FOLDER"] / f"not-a-sheet-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    frame_url = main._record_asset(user["user"]["id"], "frame", frame_path)
    frame_id = int(frame_url.split("/")[-2])

    response = client.get(
        f"/assets/{frame_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 400


def test_frame_comparison_requires_authentication(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"unauthenticated-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    sheet_url = main._record_asset(user["user"]["id"], "sprite_sheet", sheet_path)
    sheet_id = int(sheet_url.split("/")[-2])

    response = client.get(f"/assets/{sheet_id}/frame-comparison")

    assert response.status_code == 401


def test_frame_comparison_rejects_cross_user_sheet_access(isolated_client):
    client, main, folders = isolated_client
    owner = create_user(client)
    other_user = create_user(client)
    sheet_url, _ = seed_sheet(client, main, folders, owner)
    sheet_id = int(sheet_url.split("/")[-2])

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(other_user["token"]),
    )

    assert response.status_code == 404


def test_frame_comparison_returns_not_found_for_missing_associated_frame(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"missing-frame-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    sheet_url = main._record_asset(user["user"]["id"], "sprite_sheet", sheet_path)
    sheet_id = int(sheet_url.split("/")[-2])
    main._record_generation(
        user["user"]["id"],
        "walk",
        "walk",
        "completed",
        sprite_sheet_path=sheet_url,
        frame_asset_ids=[987654321],
    )

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 404
    assert "associated animation frames" in response.json()["detail"]


def test_frame_comparison_returns_not_found_when_associated_frame_file_is_missing(
    isolated_client,
):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_url, frame_ids = seed_sheet(client, main, folders, user, frame_count=1)
    sheet_id = int(sheet_url.split("/")[-2])
    with main.get_db_connection() as connection:
        frame = connection.execute(
            "SELECT name FROM user_assets WHERE id = ? AND user_id = ?",
            (frame_ids[0], user["user"]["id"]),
        ).fetchone()
    (folders["GENERATED_FRAMES_FOLDER"] / frame["name"]).unlink()

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset file not found."


def test_frame_comparison_rejects_associated_asset_that_is_not_a_frame(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"wrong-frame-type-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    non_frame_path = write_frame(
        folders["PROCESSED_FOLDER"] / f"wrong-frame-type-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    sheet_url = main._record_asset(user["user"]["id"], "sprite_sheet", sheet_path)
    non_frame_url = main._record_asset(user["user"]["id"], "processed", non_frame_path)
    sheet_id = int(sheet_url.split("/")[-2])
    non_frame_id = int(non_frame_url.split("/")[-2])
    main._record_generation(
        user["user"]["id"],
        "walk",
        "walk",
        "completed",
        sprite_sheet_path=sheet_url,
        frame_asset_ids=[non_frame_id],
    )

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 404


def test_frame_comparison_rejects_malformed_frame_ids(isolated_client):
    client, main, folders = isolated_client
    user = create_user(client)
    sheet_url, _ = seed_sheet(client, main, folders, user, frame_count=1)
    sheet_id = int(sheet_url.split("/")[-2])
    with main.get_db_connection() as connection:
        connection.execute(
            """
            UPDATE generation_records
            SET metadata = ?
            WHERE user_id = ? AND sprite_sheet_path = ?
            """,
            (
                json.dumps({"frame_asset_ids": ["1", True, -2]}),
                user["user"]["id"],
                sheet_url,
            ),
        )

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert response.status_code == 404
    assert "association" in response.json()["detail"]


def test_frame_comparison_rejects_associated_frame_owned_by_another_user(isolated_client):
    client, main, folders = isolated_client
    sheet_owner = create_user(client)
    frame_owner = create_user(client)
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"foreign-frame-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    frame_path = write_frame(
        folders["GENERATED_FRAMES_FOLDER"] / f"foreign-frame-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    sheet_url = main._record_asset(sheet_owner["user"]["id"], "sprite_sheet", sheet_path)
    frame_url = main._record_asset(frame_owner["user"]["id"], "frame", frame_path)
    sheet_id = int(sheet_url.split("/")[-2])
    frame_id = int(frame_url.split("/")[-2])
    main._record_generation(
        sheet_owner["user"]["id"],
        "walk",
        "walk",
        "completed",
        sprite_sheet_path=sheet_url,
        frame_asset_ids=[frame_id],
    )

    response = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(sheet_owner["token"]),
    )

    assert response.status_code == 404


def test_frame_comparison_matches_sheet_not_latest_generation_for_same_action(
    isolated_client,
):
    client, main, folders = isolated_client
    user = create_user(client)
    first_sheet_url, _ = seed_sheet(client, main, folders, user, frame_count=1)
    second_sheet_url, _ = seed_sheet(client, main, folders, user, frame_count=3)

    first_response = client.get(
        f"/assets/{int(first_sheet_url.split('/')[-2])}/frame-comparison",
        headers=auth(user["token"]),
    )
    second_response = client.get(
        f"/assets/{int(second_sheet_url.split('/')[-2])}/frame-comparison",
        headers=auth(user["token"]),
    )

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["frame_comparison"]["frame_count"] == 1
    assert second_response.json()["frame_comparison"]["frame_count"] == 3


def test_generate_sprite_stores_frame_asset_ids_in_matching_history_record(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    user = create_user(client)
    character_path = write_frame(
        folders["PROCESSED_FOLDER"] / f"character-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    character_url = main._record_asset(user["user"]["id"], "processed", character_path)
    frame_paths = [
        write_frame(
            folders["GENERATED_FRAMES_FOLDER"] / f"generated-{uuid4().hex}-{index}.png",
            (255, index * 100, 0, 255),
        )
        for index in range(2)
    ]
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"generated-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    monkeypatch.setattr(
        main,
        "generate_sprite",
        lambda *_args: {
            "frames": [str(path) for path in frame_paths],
            "sprite_sheet": str(sheet_path),
            "generated_video": None,
            "action": "walk",
            "frame_count": 2,
        },
    )

    generated = client.post(
        "/generate-sprite",
        headers=auth(user["token"]),
        json={"character_path": character_url, "action": "walk", "frame_count": 2},
    )
    assert generated.status_code == 200, generated.text
    assert {
        "frames",
        "sprite_sheet",
        "generated_video",
        "action_label",
        "action",
        "frame_count",
    } <= generated.json().keys()
    sheet_id = int(generated.json()["sprite_sheet"].split("/")[-2])
    comparison = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )
    assert comparison.status_code == 200, comparison.text

    with main.get_db_connection() as connection:
        history = connection.execute(
            "SELECT metadata FROM generation_records WHERE user_id = ? AND sprite_sheet_path = ?",
            (user["user"]["id"], generated.json()["sprite_sheet"]),
        ).fetchone()
    metadata = json.loads(history["metadata"])
    assert metadata["frame_asset_ids"] == [
        int(frame_url.split("/")[-2]) for frame_url in generated.json()["frames"]
    ]


def test_generate_sprite_from_prompt_stores_frame_asset_ids_in_history(
    isolated_client, monkeypatch
):
    client, main, folders = isolated_client
    user = create_user(client)
    character_path = write_frame(
        folders["GENERATED_FOLDER"] / f"prompt-character-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    processed_path = write_frame(
        folders["PROCESSED_FOLDER"] / f"prompt-processed-{uuid4().hex}.png",
        (255, 0, 0, 255),
    )
    frame_paths = [
        write_frame(
            folders["GENERATED_FRAMES_FOLDER"] / f"prompt-frame-{uuid4().hex}-{index}.png",
            (255, index * 100, 0, 255),
        )
        for index in range(2)
    ]
    sheet_path = write_frame(
        folders["SPRITE_SHEETS_FOLDER"] / f"prompt-sheet-{uuid4().hex}.png",
        (0, 0, 255, 255),
    )
    monkeypatch.setattr(
        main,
        "generate_sprite_from_prompt",
        lambda *_args: {
            "frames": [str(path) for path in frame_paths],
            "sprite_sheet": str(sheet_path),
            "generated_video": None,
            "action": "walk",
            "frame_count": 2,
            "generated_character_path": character_path,
            "processed_character_path": processed_path,
        },
    )

    generated = client.post(
        "/generate-sprite-from-prompt",
        headers=auth(user["token"]),
        json={"prompt": "pixel hero", "action": "walk", "frame_count": 2},
    )
    assert generated.status_code == 200, generated.text
    assert {
        "frames",
        "sprite_sheet",
        "generated_video",
        "action_label",
        "action",
        "frame_count",
        "generated_character_url",
        "processed_character_url",
        "video",
    } <= generated.json().keys()
    sheet_id = int(generated.json()["sprite_sheet"].split("/")[-2])
    comparison = client.get(
        f"/assets/{sheet_id}/frame-comparison",
        headers=auth(user["token"]),
    )
    assert comparison.status_code == 200, comparison.text

    with main.get_db_connection() as connection:
        history = connection.execute(
            "SELECT metadata FROM generation_records WHERE user_id = ? AND sprite_sheet_path = ?",
            (user["user"]["id"], generated.json()["sprite_sheet"]),
        ).fetchone()
    metadata = json.loads(history["metadata"])
    assert metadata["frame_asset_ids"] == [
        int(frame_url.split("/")[-2]) for frame_url in generated.json()["frames"]
    ]
