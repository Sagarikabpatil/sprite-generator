from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
import app.main as main_module


GENERATED_FOLDER = Path(__file__).resolve().parents[1] / "app" / "generated"
GENERATED_FILENAME = "generated_20260910_191641_983f4891.jpeg"


def test_generated_prompt_image_is_served_from_app_generated():
    image_path = GENERATED_FOLDER / GENERATED_FILENAME
    assert image_path.is_file()

    response = TestClient(app).get(f"/generated/{GENERATED_FILENAME}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")


def test_other_static_mounts_remain_available():
    processed_files = sorted(
        (Path(__file__).resolve().parents[1] / "app" / "processed").glob("*"),
    )
    assert processed_files

    response = TestClient(app).get(f"/processed/{processed_files[0].name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")


def test_generate_response_uses_saved_filename(monkeypatch):
    filename = "generated_test_actual_name.jpeg"
    monkeypatch.setattr(main_module, "generate_character", lambda prompt: filename)

    response = TestClient(app).post("/generate", json={"prompt": "warrior"})

    assert response.status_code == 200
    assert response.json()["image"].endswith(f"/generated/{filename}")
