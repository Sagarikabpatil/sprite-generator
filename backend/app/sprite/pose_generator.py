"""Coordinate provider-backed animation frame generation."""

from __future__ import annotations

from pathlib import Path

from app.sprite.action_taxonomy import ACTION_LOOKUP, LEGACY_ACTIONS, get_action
from app.sprite.pose_provider import GenerationMetadata, PoseRequest, get_pose_provider

SUPPORTED_ACTIONS = set(ACTION_LOOKUP) | LEGACY_ACTIONS
DEFAULT_FRAME_COUNT = 8
FRAMES_FOLDER = Path(__file__).resolve().parents[1] / "generated_frames"
_last_generation_metadata: GenerationMetadata | None = None


def generate_animation_frames(
    character_path: str,
    action: str,
    frame_count: int = DEFAULT_FRAME_COUNT,
) -> list[str]:
    """Generate saved animation frames through the configured pose provider."""
    if not character_path or not Path(character_path).is_file():
        raise FileNotFoundError("Processed character image was not found.")
    try:
        taxonomy_action = get_action(action)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if isinstance(frame_count, bool) or not 1 <= frame_count <= 64:
        raise ValueError("frame_count must be an integer between 1 and 64.")

    global _last_generation_metadata
    FRAMES_FOLDER.mkdir(parents=True, exist_ok=True)
    provider = get_pose_provider()
    frames = provider.generate_frames(
        PoseRequest(
            character_path,
            taxonomy_action["provider_action"],
            frame_count,
            taxonomy_action["prompt"],
        ),
        FRAMES_FOLDER,
    )
    _last_generation_metadata = getattr(provider, "last_generation", None)
    return frames


def get_last_generation_metadata() -> GenerationMetadata | None:
    """Return metadata from the most recent provider-backed generation."""
    return _last_generation_metadata
