from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.generation.generator import generate_character
from app.services.image_service import process_uploaded_image

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
UPLOAD_FOLDER = BASE_DIR / "app" / "uploads"
PROCESSED_FOLDER = BASE_DIR / "app" / "processed"
GENERATED_FOLDER = BASE_DIR / "app" / "generated"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_FOLDER)), name="uploads")
app.mount("/processed", StaticFiles(directory=str(PROCESSED_FOLDER)), name="processed")
app.mount("/generated", StaticFiles(directory=str(GENERATED_FOLDER)), name="generated")


class GenerateRequest(BaseModel):
    prompt: str


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
