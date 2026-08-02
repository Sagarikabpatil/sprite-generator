from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
from rembg import remove

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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="uploads")


@app.get("/")
def home():
    return {"message": "Backend is running successfully!"}


@app.get("/hello")
def hello():
    return {"message": "Hello from FastAPI 🚀"}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Remove background
    output_filename = f"no_bg_{os.path.splitext(file.filename)[0]}.png"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)

    with open(file_path, "rb") as input_file:
        input_data = input_file.read()

    output_data = remove(input_data)

    with open(output_path, "wb") as output_file:
        output_file.write(output_data)

    return {
        "original": f"http://127.0.0.1:8000/uploads/{file.filename}",
        "removed": f"http://127.0.0.1:8000/uploads/{output_filename}"
    }