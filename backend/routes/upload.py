"""
POST /api/upload

Accepts a multipart file (PNG / JPG / PDF), validates it, stores it,
then fires the pipeline as a FastAPI BackgroundTask.
Returns {job_id} immediately — the client polls GET /api/mto/{job_id}.
"""
import os
import time
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from core.config import settings
from core.exceptions import FileTooLargeError, CorruptImageError
from core.job_store import job_store
from services.pipeline import run_pipeline

router = APIRouter()

ALLOWED_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "application/pdf": ".pdf",
}

UPLOAD_DIR = Path(tempfile.gettempdir()) / "mto_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_drawing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    # ── Content-type validation ──────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. "
                   f"Accepted: PNG, JPG, PDF.",
        )

    # ── Read + size validation ───────────────────────────────────────────────
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    max_mb = settings.max_file_size_mb

    if size_mb > max_mb:
        raise FileTooLargeError(size_mb=size_mb, limit_mb=max_mb)

    # ── Save to temp file ────────────────────────────────────────────────────
    ext = ALLOWED_TYPES[file.content_type]
    safe_name = f"{int(time.time())}_{os.urandom(4).hex()}{ext}"
    temp_path = UPLOAD_DIR / safe_name
    temp_path.write_bytes(contents)

    # ── Create job + fire background pipeline ────────────────────────────────
    job_id = job_store.create_job(filename=file.filename or "drawing")
    background_tasks.add_task(run_pipeline, job_id=job_id, file_path=temp_path)

    return {"job_id": job_id, "filename": file.filename, "size_mb": round(size_mb, 2)}
