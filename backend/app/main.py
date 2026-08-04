from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

try:
    from app.services.image_service import process_uploaded_image
except ImportError:
    from services.image_service import process_uploaded_image

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

UPLOAD_FOLDER = "app/uploads"
PROCESSED_FOLDER = "app/processed"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")
app.mount("/processed", StaticFiles(directory=PROCESSED_FOLDER), name="processed")

@app.get("/")
def home():
    return {"message": "Backend is running successfully!"}


@app.get("/hello")
def hello():
    return {"message": "Hello from FastAPI 🚀"}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    return process_uploaded_image(file)
