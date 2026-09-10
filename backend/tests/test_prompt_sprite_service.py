from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import prompt_sprite_service


def test_prompt_sprite_orchestrates_generation_preprocessing_and_animation(monkeypatch, tmp_path: Path):
    generated_folder = tmp_path / "generated"
    generated_folder.mkdir()
    generated_filename = "generated_character.png"
    generated_path = generated_folder / generated_filename
    generated_path.write_bytes(b"generated")
    processed_path = tmp_path / "processed_character.png"
    calls: dict[str, object] = {}

    monkeypatch.setattr(prompt_sprite_service, "GENERATED_FOLDER", generated_folder)
    monkeypatch.setattr(prompt_sprite_service, "generate_character", lambda prompt: generated_filename)

    def fake_process(path, source_name):
        calls["process"] = (path, source_name)
        return {
            "processed_path": processed_path,
            "processed_url": "http://127.0.0.1:8000/processed/processed_character.png",
        }

    def fake_sprite(path, action, frame_count):
        calls["sprite"] = (path, action, frame_count)
        return {"frames": [], "sprite_sheet": str(tmp_path / "sheet.png"), "generated_video": None}

    monkeypatch.setattr(prompt_sprite_service, "process_image_path", fake_process)
    monkeypatch.setattr(prompt_sprite_service, "generate_sprite", fake_sprite)

    result = prompt_sprite_service.generate_sprite_from_prompt("warrior", "sword_slash", 8)

    assert calls["process"] == (generated_path, generated_filename)
    assert calls["sprite"] == (str(processed_path), "sword_slash", 8)
    assert result["generated_character_url"].endswith(f"/generated/{generated_filename}")
    assert result["processed_character_url"].endswith("/processed/processed_character.png")
    assert result["frame_count"] == 8
    assert result["action"] == "sword_slash"


def test_prompt_sprite_endpoint_returns_pipeline_urls(monkeypatch, tmp_path: Path):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"sheet")
    monkeypatch.setattr(
        "app.main.generate_sprite_from_prompt",
        lambda prompt, action, frame_count: {
            "prompt": prompt,
            "action": action,
            "frame_count": frame_count,
            "generated_character_url": "http://127.0.0.1:8000/generated/character.png",
            "processed_character_url": "http://127.0.0.1:8000/processed/processed_character.png",
            "frames": [],
            "sprite_sheet": str(sheet),
            "generated_video": None,
            "provider": "test-provider",
        },
    )

    response = TestClient(app).post(
        "/generate-sprite-from-prompt",
        json={"prompt": "warrior", "action": "sword_slash", "frame_count": 8},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_character_url"].endswith("/generated/character.png")
    assert payload["processed_character_url"].endswith("/processed/processed_character.png")
    assert payload["video"] is None


@pytest.mark.parametrize("failure", ["character", "preprocessing", "animation"])
def test_prompt_sprite_stages_fail_cleanly(monkeypatch, failure):
    if failure == "character":
        monkeypatch.setattr(prompt_sprite_service, "generate_character", lambda prompt: (_ for _ in ()).throw(RuntimeError("character failed")))
    elif failure == "preprocessing":
        monkeypatch.setattr(prompt_sprite_service, "generate_character", lambda prompt: "character.png")
        monkeypatch.setattr(prompt_sprite_service, "process_image_path", lambda path, source: (_ for _ in ()).throw(RuntimeError("preprocessing failed")))
    else:
        monkeypatch.setattr(prompt_sprite_service, "generate_character", lambda prompt: "character.png")
        monkeypatch.setattr(prompt_sprite_service, "process_image_path", lambda path, source: {"processed_path": "processed.png", "processed_url": "processed-url"})
        monkeypatch.setattr(prompt_sprite_service, "generate_sprite", lambda path, action, frame_count: (_ for _ in ()).throw(RuntimeError("animation failed")))

    with pytest.raises(RuntimeError, match=failure):
        prompt_sprite_service.generate_sprite_from_prompt("warrior", "walk", 8)
