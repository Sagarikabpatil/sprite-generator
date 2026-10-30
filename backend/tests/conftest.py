import atexit
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

bootstrap_db = Path(tempfile.gettempdir()) / f"assetai-test-bootstrap-{uuid4().hex}.sqlite"
os.environ["ASSETAI_DB_ENGINE"] = "sqlite"
os.environ["ASSETAI_DB_PATH"] = str(bootstrap_db)


def _remove_bootstrap_database() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(f"{bootstrap_db}{suffix}").unlink(missing_ok=True)


atexit.register(_remove_bootstrap_database)


@pytest.fixture
def isolated_client(monkeypatch, tmp_path: Path):
    from app import main
    from app.services import image_service, prompt_sprite_service, sprite_service

    folders = {
        "UPLOAD_FOLDER": tmp_path / "uploads",
        "PROCESSED_FOLDER": tmp_path / "processed",
        "GENERATED_FOLDER": tmp_path / "generated",
        "GENERATED_FRAMES_FOLDER": tmp_path / "generated_frames",
        "SPRITE_SHEETS_FOLDER": tmp_path / "sprite_sheets",
        "GENERATED_VIDEOS_FOLDER": tmp_path / "generated" / "videos",
    }
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.sqlite")
    for name, folder in folders.items():
        monkeypatch.setattr(main, name, folder)
    monkeypatch.setattr(
        main,
        "ASSET_STORAGE_ROOTS",
        {
            "upload": folders["UPLOAD_FOLDER"],
            "background_removed": folders["UPLOAD_FOLDER"],
            "processed": folders["PROCESSED_FOLDER"],
            "character": folders["GENERATED_FOLDER"],
            "frame": folders["GENERATED_FRAMES_FOLDER"],
            "sprite_sheet": folders["SPRITE_SHEETS_FOLDER"],
            "video": folders["GENERATED_VIDEOS_FOLDER"],
        },
    )
    monkeypatch.setattr(image_service, "UPLOAD_FOLDER", folders["UPLOAD_FOLDER"])
    monkeypatch.setattr(image_service, "PROCESSED_FOLDER", folders["PROCESSED_FOLDER"])
    monkeypatch.setattr(prompt_sprite_service, "GENERATED_FOLDER", folders["GENERATED_FOLDER"])
    monkeypatch.setattr(sprite_service, "GENERATED_FOLDER", folders["GENERATED_FOLDER"])
    monkeypatch.setattr(sprite_service, "PROCESSED_FOLDER", folders["PROCESSED_FOLDER"])
    monkeypatch.setattr(sprite_service, "FRAMES_FOLDER", folders["GENERATED_FRAMES_FOLDER"])
    monkeypatch.setattr(sprite_service, "SHEETS_FOLDER", folders["SPRITE_SHEETS_FOLDER"])
    main.initialize_database()

    with TestClient(main.app) as client:
        yield client, main, folders
