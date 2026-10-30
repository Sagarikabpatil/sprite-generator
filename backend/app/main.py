import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from app.generation.generator import ImageProviderName, generate_character
from app.generation.prompt_catalog import PROMPT_IDEAS, enrich_prompt
from app.database import (
    DatabaseConfig,
    DatabaseConnection,
    DatabaseError,
    DatabaseIntegrityError,
    connect_database,
)
from app.services.sprite_quality_service import (
    analyze_sprite_sheet,
    compare_sprite_frames,
)
from app.mysql_schema import MYSQL_SCHEMA
from app.services.image_service import ImageProcessingError, process_uploaded_image
from app.services.prompt_sprite_service import generate_sprite_from_prompt
from app.services.sprite_service import generate_sprite
from app.sprite.action_taxonomy import ACTION_GROUPS, get_action
from app.sprite.pose_provider import PoseProviderError, PoseProviderNotConfiguredError

BASE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _is_production_environment() -> bool:
    return (
        os.environ.get("RENDER", "").strip().lower() == "true"
        or os.environ.get("ASSETAI_ENV", "").strip().lower() == "production"
    )


def configure_cors(application: FastAPI) -> None:
    is_production = _is_production_environment()
    frontend_origin = os.environ.get("ASSETAI_FRONTEND_ORIGIN", "").strip()
    allowed_origins = [] if is_production else ["http://localhost:5173"]
    if frontend_origin:
        frontend_origin = frontend_origin.rstrip("/")
        parsed_origin = urlparse(frontend_origin)
        try:
            parsed_origin.port
        except ValueError as exc:
            raise ValueError(
                "ASSETAI_FRONTEND_ORIGIN must be a valid HTTP(S) origin."
            ) from exc
        if (
            "*" in frontend_origin
            or any(character.isspace() for character in frontend_origin)
            or parsed_origin.scheme not in {"http", "https"}
            or not parsed_origin.hostname
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ValueError(
                "ASSETAI_FRONTEND_ORIGIN must be a single HTTP(S) origin without "
                "a path, query, fragment, credentials, or wildcard."
            )
        if frontend_origin not in allowed_origins:
            allowed_origins.append(frontend_origin)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=(
            None if is_production else r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Asset-Filename"],
    )

app = FastAPI(
    title="AI Animation Sprite Generator API",
    version="1.0.0"
)
configure_cors(app)

UPLOAD_FOLDER = BASE_DIR / "uploads"
PROCESSED_FOLDER = APP_DIR / "processed"
GENERATED_FOLDER = APP_DIR / "generated"
GENERATED_FRAMES_FOLDER = APP_DIR / "generated_frames"
SPRITE_SHEETS_FOLDER = APP_DIR / "sprite_sheets"
GENERATED_VIDEOS_FOLDER = APP_DIR / "generated" / "videos"
DB_PATH = Path(os.environ.get("ASSETAI_DB_PATH", BASE_DIR / "app.db"))
DB_CONFIG = DatabaseConfig.from_env(
    default_sqlite_path=DB_PATH,
    require_explicit_engine=_is_production_environment(),
)

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_FRAMES_FOLDER.mkdir(parents=True, exist_ok=True)
SPRITE_SHEETS_FOLDER.mkdir(parents=True, exist_ok=True)
GENERATED_VIDEOS_FOLDER.mkdir(parents=True, exist_ok=True)

def get_db_connection() -> DatabaseConnection:
    return connect_database(DB_CONFIG, sqlite_path=DB_PATH)


def initialize_database() -> None:
    with get_db_connection() as connection:
        if connection.engine == "mysql":
            for statement in MYSQL_SCHEMA:
                connection.execute(statement)
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS generation_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                prompt TEXT,
                action TEXT,
                status TEXT NOT NULL,
                character_path TEXT,
                processed_path TEXT,
                sprite_sheet_path TEXT,
                video_path TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                asset_type TEXT NOT NULL,
                name TEXT NOT NULL,
                file_url TEXT,
                prompt TEXT,
                action TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )


def _is_valid_email(value: str) -> bool:
    return "@" in value and "." in value


def _database_datetime(value: datetime) -> str | datetime:
    if DB_CONFIG.engine == "mysql":
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.astimezone(timezone.utc).isoformat()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def _create_user_record(email: str, password: str) -> dict[str, object]:
    if not email or not _is_valid_email(email):
        raise ValueError("Please provide a valid email address.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    with get_db_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (email, password_hash, password_salt, display_name) VALUES (?, ?, ?, ?)",
            (email.lower(), password_hash, salt, email.split("@", 1)[0].title()),
        )
        user_id = cursor.lastrowid
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(user)


def _lookup_user_by_email(email: str) -> Any | None:
    with get_db_connection() as connection:
        return connection.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()


def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = _database_datetime(datetime.now(timezone.utc) + timedelta(days=30))
    with get_db_connection() as connection:
        connection.execute(
            "INSERT INTO auth_sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at),
        )
    return token


def _get_authenticated_user(request: Request) -> Any | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    if not token:
        return None
    with get_db_connection() as connection:
        session = connection.execute(
            "SELECT * FROM auth_sessions WHERE token = ? AND expires_at > ?",
            (token, _database_datetime(datetime.now(timezone.utc))),
        ).fetchone()
        if not session:
            return None
        user = connection.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        return user


def _require_authenticated_user(request: Request) -> Any:
    user = _get_authenticated_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


ASSET_STORAGE_ROOTS = {
    "upload": UPLOAD_FOLDER,
    "background_removed": UPLOAD_FOLDER,
    "processed": PROCESSED_FOLDER,
    "character": GENERATED_FOLDER,
    "frame": GENERATED_FRAMES_FOLDER,
    "sprite_sheet": SPRITE_SHEETS_FOLDER,
    "video": GENERATED_VIDEOS_FOLDER,
}


def _asset_url(asset_id: int) -> str:
    return f"/assets/{asset_id}/file"


def _asset_id_from_url(value: str) -> int:
    parsed = urlparse(value)
    segments = parsed.path.strip("/").split("/")
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or len(segments) != 3
        or segments[0] != "assets"
        or segments[2] != "file"
        or not segments[1].isdecimal()
    ):
        raise ValueError("Invalid recorded asset URL.")
    asset_id = int(segments[1])
    if asset_id <= 0 or _asset_url(asset_id) != value:
        raise ValueError("Invalid recorded asset URL.")
    return asset_id


def _resolve_asset_path(asset_type: str, path: str | Path) -> Path:
    storage_root = ASSET_STORAGE_ROOTS.get(asset_type)
    if storage_root is None:
        raise ValueError(f"Unsupported asset type: {asset_type}")
    try:
        trusted_root = Path(storage_root).resolve(strict=True)
        asset_path = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Asset is outside its expected storage directory.") from exc
    if (
        not asset_path.is_relative_to(trusted_root)
        or asset_path == trusted_root
        or asset_path.parent != trusted_root
        or not asset_path.is_file()
    ):
        raise ValueError("Asset is outside its expected storage directory.")
    return asset_path


def _record_assets(
    user_id: int,
    assets: list[tuple[str, str | Path, str | None, str | None]],
) -> list[str]:
    resolved_assets = [
        (asset_type, _resolve_asset_path(asset_type, path), prompt, action)
        for asset_type, path, prompt, action in assets
    ]
    recorded_urls: list[str] = []
    with get_db_connection() as connection:
        for asset_type, asset_path, prompt, action in resolved_assets:
            shared_file = connection.execute(
                "SELECT 1 FROM user_assets WHERE asset_type = ? AND name = ? AND user_id != ? LIMIT 1",
                (asset_type, asset_path.name, user_id),
            ).fetchone()
            if shared_file:
                raise ValueError("Asset filename is already associated with another user.")
            cursor = connection.execute(
                "INSERT INTO user_assets (user_id, asset_type, name, file_url, prompt, action) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, asset_type, asset_path.name, "", prompt, action),
            )
            asset_id = int(cursor.lastrowid)
            file_url = _asset_url(asset_id)
            connection.execute(
                "UPDATE user_assets SET file_url = ? WHERE id = ?",
                (file_url, asset_id),
            )
            recorded_urls.append(file_url)
    return recorded_urls


def _record_asset(
    user_id: int,
    asset_type: str,
    path: str | Path,
    *,
    prompt: str | None = None,
    action: str | None = None,
) -> str:
    return _record_assets(user_id, [(asset_type, path, prompt, action)])[0]


def _cleanup_upload_outputs(filename: str) -> list[Path]:
    stem = Path(filename).stem
    outputs = (
        (UPLOAD_FOLDER, filename),
        (UPLOAD_FOLDER, f"no_bg_{stem}.png"),
        (PROCESSED_FOLDER, f"processed_{stem}.png"),
    )
    failed_paths: list[Path] = []
    for root, name in outputs:
        try:
            trusted_root = Path(root).resolve(strict=True)
            output_path = trusted_root / name
            if output_path.resolve(strict=True).is_relative_to(trusted_root) and output_path.is_file():
                output_path.unlink()
        except FileNotFoundError:
            continue
        except (OSError, RuntimeError):
            failed_paths.append(Path(root) / name)
    return failed_paths


def _record_generation(
    user_id: int,
    prompt: str,
    action: str,
    status: str,
    **fields: object,
) -> None:
    metadata = json.dumps(fields, ensure_ascii=False)
    with get_db_connection() as connection:
        connection.execute(
            "INSERT INTO generation_records (user_id, prompt, action, status, character_path, processed_path, sprite_sheet_path, video_path, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                prompt,
                action,
                status,
                fields.get("character_path"),
                fields.get("processed_path"),
                fields.get("sprite_sheet_path"),
                fields.get("video_path"),
                metadata,
            ),
        )


def _get_owned_asset(user_id: int, asset_id: int) -> tuple[Any, Path]:
    with get_db_connection() as connection:
        asset = connection.execute(
            "SELECT * FROM user_assets WHERE id = ? AND user_id = ?",
            (asset_id, user_id),
        ).fetchone()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")

    directory = ASSET_STORAGE_ROOTS.get(asset["asset_type"])
    filename = asset["name"]
    if (
        directory is None
        or not filename
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise HTTPException(status_code=404, detail="Asset not found.")
    with get_db_connection() as connection:
        shared_file = connection.execute(
            "SELECT 1 FROM user_assets WHERE asset_type = ? AND name = ? AND user_id != ? LIMIT 1",
            (asset["asset_type"], filename, user_id),
        ).fetchone()
    if shared_file:
        raise HTTPException(status_code=404, detail="Asset not found.")
    try:
        asset_path = _resolve_asset_path(asset["asset_type"], Path(directory) / filename)
    except ValueError:
        raise HTTPException(status_code=404, detail="Asset file not found.")
    return asset, asset_path


def _owned_history_url(user_id: int, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    segments = parsed.path.strip("/").split("/")
    if parsed.query or parsed.fragment or len(segments) != 3 or segments[0] != "assets" or segments[2] != "file":
        return None
    try:
        asset_id = int(segments[1])
    except ValueError:
        return None
    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT id FROM user_assets WHERE id = ? AND user_id = ?",
            (asset_id, user_id),
        ).fetchone()
    return _asset_url(row["id"]) if row else None


def _register_sprite_assets(
    user_id: int,
    result: dict[str, object],
    prompt: str,
    action: str,
) -> tuple[dict[str, object], list[int]]:
    frame_urls: list[str] = []
    frame_asset_ids: list[int] = []
    for path in result["frames"]:
        frame_url = _record_asset(user_id, "frame", path, prompt=prompt, action=action)
        frame_urls.append(frame_url)
        frame_asset_ids.append(_asset_id_from_url(frame_url))

    sheet_url = _record_asset(
        user_id, "sprite_sheet", str(result["sprite_sheet"]), prompt=prompt, action=action
    )
    video_path = result.get("generated_video")
    video_url = (
        _record_asset(user_id, "video", str(video_path), prompt=prompt, action=action)
        if video_path
        else None
    )
    response = {
        **result,
        "frames": frame_urls,
        "sprite_sheet": sheet_url,
        "generated_video": video_url,
        "action_label": get_action(action)["label"],
    }
    return response, frame_asset_ids


initialize_database()


class GenerateRequest(BaseModel):
    prompt: str
    provider: ImageProviderName | None = None
    allow_cloudflare_fallback: bool | None = None


class GenerateSpriteRequest(BaseModel):
    character_path: str
    action: str = "idle"
    frame_count: int = 8


class GenerateSpriteFromPromptRequest(BaseModel):
    prompt: str
    action: str = "idle"
    frame_count: int = 8
    provider: ImageProviderName | None = None
    allow_cloudflare_fallback: bool | None = None


class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/")
def home():
    return {"message": "Backend is running successfully!"}


@app.get("/hello")
def hello():
    return {"message": "Hello from FastAPI 🚀"}


@app.get("/actions")
def actions_endpoint():
    return [
        {
            "value": category,
            "label": category.replace("_", " ").title(),
            "actions": [
                {
                    "label": action["label"],
                    "value": action["value"],
                    "description": action["prompt"],
                }
                for action in actions
            ],
        }
        for category, actions in ACTION_GROUPS.items()
    ]


@app.get("/prompt-ideas")
def prompt_ideas_endpoint():
    return PROMPT_IDEAS


@app.post("/auth/signup")
async def signup_endpoint(payload: SignupRequest):
    try:
        user = _create_user_record(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatabaseIntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc

    token = _create_session(int(user["id"]))
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
        "token": token,
    }


@app.post("/auth/login")
async def login_endpoint(payload: LoginRequest):
    user = _lookup_user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    password_hash = _hash_password(payload.password, user["password_salt"])
    if user["password_hash"] != password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = _create_session(int(user["id"]))
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
        "token": token,
    }


@app.post("/auth/logout", status_code=204)
async def logout_endpoint(request: Request):
    _require_authenticated_user(request)
    token = request.headers["Authorization"].split(" ", 1)[1].strip()
    with get_db_connection() as connection:
        connection.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    return Response(status_code=204)


@app.get("/auth/me")
async def me_endpoint(request: Request):
    user = _require_authenticated_user(request)
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
    }


@app.get("/history")
async def history_endpoint(request: Request):
    user = _require_authenticated_user(request)
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM generation_records WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "prompt": row["prompt"],
            "action": row["action"],
            "status": row["status"],
            "character_path": _owned_history_url(user["id"], row["character_path"]),
            "processed_path": _owned_history_url(user["id"], row["processed_path"]),
            "sprite_sheet_path": _owned_history_url(user["id"], row["sprite_sheet_path"]),
            "video_path": _owned_history_url(user["id"], row["video_path"]),
            "metadata": {
                key: value
                for key, value in json.loads(row["metadata"] or "{}").items()
                if "path" not in key.lower() and not isinstance(value, (Path, dict, list))
            },
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@app.get("/assets/{asset_id}/quality")
async def sprite_quality_endpoint(asset_id: int, request: Request):
    """Analyze an owned sprite sheet or animation frame."""
    user = _require_authenticated_user(request)
    asset, asset_path = _get_owned_asset(user["id"], asset_id)

    if asset["asset_type"] not in {"sprite_sheet", "frame"}:
        raise HTTPException(
            status_code=400,
            detail="Choose a sprite sheet or animation frame to analyze.",
        )

    try:
        report = analyze_sprite_sheet(asset_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "asset_id": asset_id,
        "asset_name": asset["name"],
        "asset_type": asset["asset_type"],
        "quality_report": report,
    }



@app.get("/assets/{asset_id}/frame-comparison")
async def sprite_frame_comparison_endpoint(
    asset_id: int,
    request: Request,
):
    """Compare frames associated with a sprite sheet."""
    user = _require_authenticated_user(request)
    asset, _ = _get_owned_asset(user["id"], asset_id)

    if asset["asset_type"] != "sprite_sheet":
        raise HTTPException(
            status_code=400,
            detail="Choose a sprite sheet to compare its animation frames.",
        )

    with get_db_connection() as connection:
        generation = connection.execute(
            """
            SELECT metadata
            FROM generation_records
            WHERE user_id = ? AND sprite_sheet_path = ? AND status = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user["id"], _asset_url(asset_id), "completed"),
        ).fetchone()

    if generation is None:
        raise HTTPException(
            status_code=404,
            detail="No saved frame association exists for this sprite sheet.",
        )
    try:
        metadata = json.loads(generation["metadata"] or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=404,
            detail="No saved frame association exists for this sprite sheet.",
        ) from exc
    frame_asset_ids = metadata.get("frame_asset_ids") if isinstance(metadata, dict) else None
    if (
        not isinstance(frame_asset_ids, list)
        or not frame_asset_ids
        or any(type(frame_id) is not int or frame_id <= 0 for frame_id in frame_asset_ids)
    ):
        raise HTTPException(
            status_code=404,
            detail="No saved frame association exists for this sprite sheet.",
        )

    placeholders = ", ".join("?" for _ in frame_asset_ids)
    with get_db_connection() as connection:
        frame_rows = connection.execute(
            f"""
            SELECT id
            FROM user_assets
            WHERE user_id = ? AND asset_type = 'frame' AND id IN ({placeholders})
            """,
            (user["id"], *frame_asset_ids),
        ).fetchall()
    owned_frame_ids = {row["id"] for row in frame_rows}
    if len(owned_frame_ids) != len(frame_asset_ids) or owned_frame_ids != set(frame_asset_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more associated animation frames were not found.",
        )

    frame_paths = [
        _get_owned_asset(user["id"], frame_id)[1] for frame_id in frame_asset_ids
    ]
    try:
        comparison = compare_sprite_frames(frame_paths)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="An associated animation frame was not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "asset_id": asset_id,
        "asset_name": asset["name"],
        "frame_comparison": comparison,
    }



@app.get("/assets")
async def assets_endpoint(request: Request):
    auth_user = _require_authenticated_user(request)
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM user_assets WHERE user_id = ? ORDER BY created_at DESC",
            (auth_user["id"],),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "asset_type": row["asset_type"],
            "name": row["name"],
            "file_url": _asset_url(row["id"]),
            "prompt": row["prompt"],
            "action": row["action"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@app.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    user = _require_authenticated_user(request)
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    allowed_types = {
        ".png": {"image/png"},
        ".jpg": {"image/jpeg", "image/jpg"},
        ".jpeg": {"image/jpeg", "image/jpg"},
        ".webp": {"image/webp"},
    }
    if suffix not in allowed_types or (file.content_type or "").lower() not in allowed_types[suffix]:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPG, JPEG, or WEBP image.")
    file.file.seek(0, os.SEEK_END)
    if file.file.tell() > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image uploads must be 10 MB or smaller.")
    file.file.seek(0)
    safe_name = f"upload_{uuid4().hex}{suffix}"
    try:
        result = process_uploaded_image(file, filename=safe_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImageProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to store or process the uploaded image.") from exc

    try:
        original_url, removed_url, processed_url = _record_assets(
            user["id"],
            [
                ("upload", result["original_path"], None, None),
                ("background_removed", result["removed_path"], None, None),
                ("processed", result["processed_path"], None, None),
            ],
        )
    except (ValueError, DatabaseError) as exc:
        failed_cleanup = _cleanup_upload_outputs(safe_name)
        if failed_cleanup:
            raise HTTPException(
                status_code=500,
                detail="Asset recording failed and some temporary upload files could not be removed.",
            ) from exc
        raise HTTPException(
            status_code=500,
            detail="Uploaded files could not be recorded; the new upload files were removed.",
        ) from exc
    return {"original": original_url, "removed": removed_url, "processed": processed_url}


@app.get("/assets/{asset_id}/file")
async def download_asset(asset_id: int, request: Request):
    user = _require_authenticated_user(request)
    _, asset_path = _get_owned_asset(user["id"], asset_id)
    return FileResponse(
        path=asset_path,
        filename=asset_path.name,
        media_type={
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
        }.get(asset_path.suffix.lower(), "application/octet-stream"),
        headers={"X-Asset-Filename": asset_path.name},
    )


@app.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: int, request: Request):
    user = _require_authenticated_user(request)
    asset, asset_path = _get_owned_asset(user["id"], asset_id)
    with get_db_connection() as connection:
        connection.execute(
            "DELETE FROM user_assets WHERE id = ? AND user_id = ?",
            (asset_id, user["id"]),
        )
        remaining = connection.execute(
            "SELECT 1 FROM user_assets WHERE asset_type = ? AND name = ? LIMIT 1",
            (asset["asset_type"], asset["name"]),
        ).fetchone()
    if remaining is None and asset_path.is_file():
        asset_path.unlink()
    return Response(status_code=204)


@app.post("/generate")
async def generate_character_endpoint(request: Request, payload: GenerateRequest):
    user = _require_authenticated_user(request)
    prompt = payload.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        if payload.provider is not None or payload.allow_cloudflare_fallback is not None:
            filename = generate_character(
                prompt,
                payload.provider,
                payload.allow_cloudflare_fallback,
            )
        else:
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

    image_url = _record_asset(
        user["id"], "character", GENERATED_FOLDER / filename, prompt=prompt, action="character"
    )
    _record_generation(user["id"], prompt, "character", "completed", character_path=image_url)

    return {
        "status": "success",
        "prompt": prompt,
        "original_prompt": prompt,
        "enhanced_prompt": enrich_prompt(prompt),
        "image": image_url,
    }


@app.post("/generate-sprite")
async def generate_sprite_endpoint(request: Request, payload: GenerateSpriteRequest):
    """Generate an animation sequence from an existing character asset."""
    user = _require_authenticated_user(request)
    action = payload.action.strip().lower()
    try:
        get_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    asset_path = urlparse(payload.character_path)
    asset_segments = asset_path.path.strip("/").split("/")
    try:
        if len(asset_segments) != 3 or asset_segments[0] != "assets" or asset_segments[2] != "file" or asset_path.query:
            raise ValueError("Invalid asset URL.")
        asset_id = int(asset_segments[1])
    except (ValueError, IndexError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Choose one of your uploaded character assets.") from exc
    character_asset, character_path = _get_owned_asset(user["id"], asset_id)
    if character_asset["asset_type"] != "processed":
        raise HTTPException(
            status_code=400,
            detail="Choose a processed character image before generating an animation.",
        )
    try:
        result = generate_sprite(
            str(character_path),
            action,
            payload.frame_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PoseProviderNotConfiguredError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    except PoseProviderError as exc:
        try:
            _record_generation(
                user["id"],
                "",
                action,
                "failed",
                character_path=payload.character_path,
                processed_path=payload.character_path,
                error=str(exc),
            )
        except DatabaseError as db_exc:
            print(f"Failed to record animation failure in history: {db_exc}")
        raise HTTPException(status_code=502, detail=str(exc)
    ) from exc

    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response, frame_asset_ids = _register_sprite_assets(
        user["id"], result, "", action
    )
    _record_generation(
        user["id"],
        "",
        action,
        "completed",
        character_path=payload.character_path,
        processed_path=payload.character_path,
        sprite_sheet_path=response["sprite_sheet"],
        video_path=response["generated_video"],
        frame_asset_ids=frame_asset_ids,
    )
    return response


@app.post("/generate-sprite-from-prompt")
async def generate_sprite_from_prompt_endpoint(request: Request, payload: GenerateSpriteFromPromptRequest):
    """Generate a character from text and immediately build its sprite animation."""
    user = _require_authenticated_user(request)
    prompt = payload.prompt.strip()
    action = payload.action.strip().lower()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        get_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if payload.provider is not None or payload.allow_cloudflare_fallback is not None:
            result = generate_sprite_from_prompt(
                prompt,
                action,
                payload.frame_count,
                payload.provider,
                payload.allow_cloudflare_fallback,
            )
        else:
            result = generate_sprite_from_prompt(prompt, action, payload.frame_count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PoseProviderNotConfiguredError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except PoseProviderError as exc:
        try:
             _record_generation(
                user["id"],
                prompt,
                action,
                "failed",
                error=str(exc),
            )
        except DatabaseError as db_exc:
            print(f"Failed to record prompt animation failure in history: {db_exc}")

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Prompt-to-sprite generation failed. Please try a different prompt.",
        ) from exc

    character_url = _record_asset(
        user["id"], "character", result["generated_character_path"], prompt=prompt, action=action
    )
    processed_url = _record_asset(
        user["id"], "processed", result["processed_character_path"], prompt=prompt, action=action
    )
    response, frame_asset_ids = _register_sprite_assets(
        user["id"], result, prompt, action
    )
    _record_generation(
        user["id"],
        prompt,
        action,
        "completed",
        character_path=character_url,
        processed_path=processed_url,
        sprite_sheet_path=response["sprite_sheet"],
        video_path=response["generated_video"],
        frame_asset_ids=frame_asset_ids,
    )
    response["generated_character_url"] = character_url
    response["processed_character_url"] = processed_url
    response["video"] = response["generated_video"]
    response.pop("generated_character_path", None)
    response.pop("processed_character_path", None)
    return response