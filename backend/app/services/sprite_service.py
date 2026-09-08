"""Application service for generating animation frames and sprite sheets."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4
from urllib.parse import unquote, urlparse

from app.sprite.animation import create_animation_sequence
from app.sprite.pose_generator import generate_animation_frames, get_last_generation_metadata
from app.sprite.sheet_builder import build_sprite_sheet

BASE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_FOLDER = BASE_DIR / "processed"
GENERATED_FOLDER = BASE_DIR / "generated"
FRAMES_FOLDER = BASE_DIR / "generated_frames"
SHEETS_FOLDER = BASE_DIR / "sprite_sheets"


def resolve_character_path(character_path: str | None) -> Path:
    """Resolve a supplied static asset, or use the newest processed image."""
    if character_path:
        parsed = urlparse(character_path)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            asset_path = unquote(parsed.path)
        else:
            asset_path = unquote(character_path.split("?", 1)[0]).replace("\\", "/")

        route, separator, relative_name = asset_path.partition("/processed/")
        if separator:
            base_folder = PROCESSED_FOLDER
        else:
            route, separator, relative_name = asset_path.partition("/generated/")
            base_folder = GENERATED_FOLDER

        if separator:
            relative_path = Path(relative_name)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise FileNotFoundError("The requested character image was not found.")
            candidate = base_folder / relative_path
        else:
            local_path = Path(asset_path)
            candidate = local_path if local_path.is_absolute() else PROCESSED_FOLDER / local_path.name
        if not candidate.is_file():
            raise FileNotFoundError("The requested character image was not found.")
        return candidate

    candidates = [path for path in PROCESSED_FOLDER.iterdir() if path.is_file()]
    if not candidates:
        raise FileNotFoundError("No processed character image is available.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def generate_sprite(character_path: str | None, action: str, frame_count: int) -> dict[str, object]:
    """Run frame generation, validation, sequencing, and sheet assembly."""
    character = resolve_character_path(character_path)
    frame_paths = generate_animation_frames(str(character), action, frame_count)
    sequence = create_animation_sequence(action, frame_paths)
    if sequence["frame_count"] != frame_count:
        raise ValueError(
            f"Expected {frame_count} generated frames, received {sequence['frame_count']}."
        )
    SHEETS_FOLDER.mkdir(parents=True, exist_ok=True)
    filename = f"sheet_{action}_{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}.png"
    sheet_path = build_sprite_sheet(sequence["frames"], str(SHEETS_FOLDER / filename))
    metadata = get_last_generation_metadata()
    return {
        **sequence,
        "sprite_sheet": sheet_path,
        "generated_video": metadata.video_path if metadata else None,
        "provider": "HuggingFace MiniMaxAI/MiniMax-H3-Turbo-Lora",
        "generation_report": metadata.report if metadata else "",
        "refined_prompt": metadata.refined_prompt if metadata else "",
    }
