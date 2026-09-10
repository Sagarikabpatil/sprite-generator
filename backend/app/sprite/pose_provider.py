"""Provider boundary for AI-generated animation poses."""

from __future__ import annotations

import inspect
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.sprite.video_frames import extract_video_frames
from app.sprite.action_taxonomy import get_action

try:
    from gradio_client import Client, handle_file
except ImportError:  # Keep unrelated API routes importable if the optional dependency is absent.
    Client = None
    handle_file = None


@dataclass(frozen=True)
class PoseRequest:
    """Provider-independent inputs for one animation request."""

    character_path: str
    action: str
    frame_count: int
    prompt: str | None = None


class PoseProvider(Protocol):
    """Interface for a model that can generate consistent pose frames."""

    def generate_frames(self, request: PoseRequest, output_dir: Path) -> list[str]:
        """Generate and save animation frames."""


class PoseProviderNotConfiguredError(RuntimeError):
    """Raised until a consistent pose-generation model is configured."""


class PoseProviderError(RuntimeError):
    """Raised when the configured cloud pose provider cannot generate output."""


class UnconfiguredPoseProvider:
    """Explicit placeholder; it never fabricates animation output."""

    def generate_frames(self, request: PoseRequest, output_dir: Path) -> list[str]:
        raise PoseProviderNotConfiguredError(
            "Animation pose generation is not configured yet. "
            "Add a provider that can generate consistent character poses."
        )


ACTION_PROMPTS = {
    "idle": "idling in place",
    "walk": "walking in place. Show a natural repeating walking cycle",
    "run": "running in place. Show a natural repeating running cycle",
    "jump": "performing a repeating jump",
    "attack": "performing a clear attack animation",
}


@dataclass(frozen=True)
class GenerationMetadata:
    """Useful provider output metadata retained by the animation service."""

    video_path: str
    report: str
    refined_prompt: str


class HuggingFaceAnimationProvider:
    """Generate animation video through MiniMax's Hugging Face Gradio Space."""

    space = "MiniMaxAI/MiniMax-H3-Turbo-Lora"
    canvas = "960x544 · 16:9 fast"
    duration_seconds = 5.0
    steps = 6.0
    seed = 42.0
    lora = "larry"

    def __init__(self) -> None:
        if Client is None:
            raise PoseProviderError(
                "gradio_client is not installed. Install backend requirements before generating sprites."
            )
        token = os.getenv("HF_TOKEN")
        client_kwargs: dict[str, object] = {}
        if token:
            parameters = inspect.signature(Client).parameters
            if "oauth_token" in parameters:
                client_kwargs["oauth_token"] = token
            elif "token" in parameters:
                client_kwargs["token"] = token
            else:
                raise PoseProviderError(
                    "The installed gradio_client does not support HF_TOKEN authentication."
                )
        try:
            self.client = Client(self.space, **client_kwargs)
        except Exception as exc:
            raise PoseProviderError(
                f"Unable to connect to Hugging Face Space {self.space}: {exc}"
            ) from exc
        self.last_generation: GenerationMetadata | None = None

    @staticmethod
    def _prompt(action: str, motion_override: str | None = None) -> str:
        action_definition = get_action(action)
        motion = motion_override or action_definition["prompt"]
        return (
            f"Create a clean 2D game sprite animation of the provided character {motion}. "
            "Keep the character identity, clothing, colors, proportions and art style "
            "consistent throughout the animation. Keep the camera fixed and the character "
            "centered. Use a simple transparent-looking/clean background suitable for "
            "extracting game sprite frames. Do not change the user's character design."
        )

    def generate_frames(self, request: PoseRequest, output_dir: Path) -> list[str]:
        character_path = Path(request.character_path)
        if not character_path.is_file():
            raise FileNotFoundError(f"Character image was not found: {character_path}")
        try:
            action_definition = get_action(request.action)
        except ValueError as exc:
            raise PoseProviderError(str(exc)) from exc

        try:
            image_input = handle_file(character_path)
            output_video, report, refined_prompt = self.client.predict(
                self._prompt(request.action, request.prompt),
                image_input,
                image_input,
                self.canvas,
                self.duration_seconds,
                self.steps,
                self.seed,
                False,
                self.lora,
                api_name="/output_video",
            )
        except Exception as exc:
            raise PoseProviderError(
                f"MiniMax animation generation failed at /output_video: {exc}"
            ) from exc

        if isinstance(output_video, dict):
            output_video = output_video.get("path") or output_video.get("url")
        if not output_video or not Path(str(output_video)).is_file():
            raise PoseProviderError("MiniMax returned no usable output video file.")

        video_dir = output_dir.parent / "generated" / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        destination = video_dir / f"animation_{action_definition['value']}_{uuid4().hex}.mp4"
        try:
            shutil.copy2(str(output_video), destination)
        except OSError as exc:
            raise PoseProviderError(f"Failed to save generated video: {exc}") from exc

        self.last_generation = GenerationMetadata(
            str(destination), str(report or ""), str(refined_prompt or "")
        )
        return extract_video_frames(destination, output_dir, request.frame_count)


def get_pose_provider() -> PoseProvider:
    """Return the active provider boundary for the animation pipeline."""
    return HuggingFaceAnimationProvider()
