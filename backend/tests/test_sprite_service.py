from pathlib import Path

import pytest

from app.services.sprite_service import resolve_character_path


PROCESSED_FOLDER = Path(__file__).resolve().parents[1] / "app" / "processed"


def test_resolve_processed_url_to_existing_local_file():
    character_path = (
        "http://127.0.0.1:8000/processed/processed_spiderman%20wallpaper.png"
    )

    resolved = resolve_character_path(character_path)

    assert resolved == PROCESSED_FOLDER / "processed_spiderman wallpaper.png"
    assert resolved.is_file()


def test_resolve_missing_processed_url_raises_expected_error():
    with pytest.raises(
        FileNotFoundError,
        match="The requested character image was not found\\.",
    ):
        resolve_character_path(
            "http://127.0.0.1:8000/processed/missing%20character.png"
        )