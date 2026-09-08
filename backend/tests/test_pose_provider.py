from pathlib import Path

from app.sprite import pose_provider
from app.sprite.pose_provider import HuggingFaceAnimationProvider, PoseRequest


class FakeClient:
    def __init__(self, video_path: Path):
        self.video_path = video_path
        self.arguments = None

    def predict(self, *arguments, **kwargs):
        self.arguments = (arguments, kwargs)
        return str(self.video_path), "report", "refined prompt"


def test_provider_uses_gradio_file_data_for_both_images(monkeypatch, tmp_path: Path):
    character_path = tmp_path / "processed_spiderman wallpaper.png"
    character_path.write_bytes(b"image")
    video_path = tmp_path / "generated.mp4"
    video_path.write_bytes(b"video")
    fake_client = FakeClient(video_path)
    provider = object.__new__(HuggingFaceAnimationProvider)
    provider.client = fake_client
    provider.last_generation = None
    expected_image = {
        "path": str(character_path),
        "meta": {"_type": "gradio.FileData"},
        "orig_name": character_path.name,
    }
    monkeypatch.setattr(
        pose_provider,
        "extract_video_frames",
        lambda video, output, frame_count: [],
    )

    provider.generate_frames(PoseRequest(str(character_path), "walk", 8), tmp_path / "frames")

    arguments, kwargs = fake_client.arguments
    assert arguments[1] == expected_image
    assert arguments[2] == expected_image
    assert arguments[1] is arguments[2]
    assert kwargs == {"api_name": "/output_video"}