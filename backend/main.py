"""
Isometric MTO Generator — FastAPI Backend
Entry point: uvicorn main:app --reload
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routes import upload, mto, health
from core.exceptions import MissingAPIKeyError, CorruptImageError, FileTooLargeError

# Configure logging so pipeline steps are visible in console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Isometric MTO Generator API",
    description="Upload a piping isometric drawing and get a structured Material Take-Off",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(mto.router, prefix="/api", tags=["mto"])


# ── Global exception handlers ────────────────────────────────────────────────
@app.exception_handler(MissingAPIKeyError)
async def missing_key_handler(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "MISSING_API_KEY"})


@app.exception_handler(CorruptImageError)
async def corrupt_image_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc), "code": "CORRUPT_IMAGE"})


@app.exception_handler(FileTooLargeError)
async def file_too_large_handler(request, exc):
    return JSONResponse(status_code=413, content={"detail": str(exc), "code": "FILE_TOO_LARGE"})


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again.", "code": "INTERNAL_ERROR"},
    )
