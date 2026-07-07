"""
Pipeline orchestrator.

Currently calls mock_pipeline — real AI pipeline added in Sprint 3.
This structure means routes never need to change; just swap the inner call.
"""
import time
from pathlib import Path

from core.config import settings
from core.job_store import job_store
from models.mto import MTOResult
from services.mock_pipeline import generate_mock_mto


def run_pipeline(job_id: str, file_path: Path) -> None:
    """Called as a FastAPI BackgroundTask. Writes result to job_store."""
    start = time.time()
    try:
        # Sprint 3 will add: if settings.has_api_key → real pipeline
        # For now, always mock so Sprint 0 is fully testable
        result: MTOResult = generate_mock_mto(filename=file_path.name)
        result.processing_time_s = round(time.time() - start, 2)
        job_store.complete_job(job_id, result)
    except Exception as exc:
        job_store.fail_job(job_id, str(exc))
    finally:
        # Clean up temp file
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass
