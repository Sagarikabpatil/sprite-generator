from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.generation.generator import generate_character
from app.services.image_service import process_uploaded_image
from app.services.sprite_service import generate_sprite
from app.sprite.pose_provider import PoseProviderError, PoseProviderNotConfiguredError

app = FastAPI(
    title="AI Animation Sprite Generator API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_FOLDER = BASE_DIR / "uploads"
PROCESSED_FOLDER = Path(__file__).resolve().parent / "processed"
GENERATED_FOLDER = BASE_DIR / "generated"
GENERATED_FRAMES_FOLDER = Path(__file__).resolve().parent / "generated_frames"
SPRITE_SHEETS_FOLDER = Path(__file__).resolve().parent / "sprite_sheets"
GENERATED_VIDEOS_FOLDER = Path(__file__).resolve().parent / "generated" / "videos"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_FRAMES_FOLDER.mkdir(parents=True, exist_ok=True)
SPRITE_SHEETS_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_VIDEOS_FOLDER.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_FOLDER)), name="uploads")
app.mount("/processed", StaticFiles(directory=str(PROCESSED_FOLDER)), name="processed")
app.mount("/generated", StaticFiles(directory=str(GENERATED_FOLDER)), name="generated")
app.mount("/generated_frames", StaticFiles(directory=str(GENERATED_FRAMES_FOLDER)), name="generated_frames")
app.mount("/sprite_sheets", StaticFiles(directory=str(SPRITE_SHEETS_FOLDER)), name="sprite_sheets")
app.mount("/generated_videos", StaticFiles(directory=str(GENERATED_VIDEOS_FOLDER)), name="generated_videos")


class GenerateRequest(BaseModel):
    prompt: str


class GenerateSpriteRequest(BaseModel):
    character_path: str | None = None
    action: str = "idle"
    frame_count: int = 8


@app.get("/")
def home():
    return {"message": "Backend is running successfully!"}


@app.get("/hello")
def hello():
    return {"message": "Hello from FastAPI 🚀"}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    return process_uploaded_image(file)


@app.post("/generate")
async def generate_character_endpoint(request: GenerateRequest):
    prompt = request.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        filename = generate_character(prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate character image. Please try a different prompt.",
        ) from exc

    return {
        "status": "success",
        "prompt": prompt,
        "image": f"http://127.0.0.1:8000/generated/{filename}",
    }


@app.post("/generate-sprite")
async def generate_sprite_endpoint(request: GenerateSpriteRequest):
    """Generate an animation sequence from an existing character asset."""
    try:
        result = generate_sprite(
            request.character_path,
            request.action.strip().lower(),
            request.frame_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PoseProviderNotConfiguredError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except PoseProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        **result,
        "frames": [
            f"http://127.0.0.1:8000/generated_frames/{Path(path).name}"
            for path in result["frames"]
        ],
        "sprite_sheet": (
            "http://127.0.0.1:8000/sprite_sheets/"
            f"{Path(result['sprite_sheet']).name}"
        ),
        "generated_video": (
            "http://127.0.0.1:8000/generated_videos/"
            f"{quote(Path(result['generated_video']).name, safe='')}"
            if result.get("generated_video")
            else None
        ),
    }