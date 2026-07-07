"""
Pipeline orchestrator — full implementation.

Flow:
  1. Pre-process: load file, convert PDF→PNG, resize, enhance, crop regions
  2. OCR: Tesseract on title block crop
  3. Pass A: Gemini full image → symbols + meta
  4. Pass B: Gemini BOM crop → table rows
  5. Reconcile: merge + derive + validate
  6. Return MTOResult

Falls back to mock pipeline if:
  - GEMINI_API_KEY is not set
  - Gemini API call fails (with a logged warning)
"""
import logging
import time
import traceback
from pathlib import Path

from core.config import settings
from core.exceptions import MissingAPIKeyError
from core.job_store import job_store
from models.mto import MTOResult
from services.mock_pipeline import generate_mock_mto

logger = logging.getLogger(__name__)


def run_pipeline(job_id: str, file_path: Path) -> None:
    """Called as a FastAPI BackgroundTask. Writes result to job_store."""
    start = time.time()
    try:
        result = _execute(file_path, job_id)
        result.processing_time_s = round(time.time() - start, 2)
        job_store.complete_job(job_id, result)
        logger.info(f"[{job_id[:8]}] Pipeline done in {result.processing_time_s}s — source={result.source}, items={len(result.items)}")
    except Exception as e:
        logger.error(f"[{job_id}] Pipeline FAILED: {e}", exc_info=True)
        job_store.fail_job(job_id, str(e))
    finally:
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass


def _execute(file_path: Path, job_id: str) -> MTOResult:
    """The actual pipeline sequence."""
    from services.image_preprocess import preprocess_for_gemini
    from services.ocr_title import extract_title_block_meta
    from services.gemini_client import pass_a_extract, pass_b_extract
    from services.reconciliation import reconcile

    # 1. Preprocess (converts PDF to PNG, resizing)
    logger.info(f"Step 1: Preprocessing {file_path.name}")
    full_bytes, bom_bytes, page_count = preprocess_for_gemini(file_path)
    
    # Save the processed PNG so the frontend can load it (fixes the PDF preview issue)
    import tempfile
    png_path = Path(tempfile.gettempdir()) / "mto_uploads" / f"{job_id}.png"
    png_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.write_bytes(full_bytes)

    from PIL import Image
    import io
    img = Image.open(io.BytesIO(full_bytes))
    title_crop = img.crop((int(img.size[0] * 0.60), 0, img.size[0], int(img.size[1] * 0.40)))
    logger.info(f"  Image size: {img.size}, full={len(full_bytes)//1024}KB, bom={len(bom_bytes)//1024}KB")

    # ── Step 2: Tesseract OCR ─────────────────────────────────────────────────
    logger.info("Step 2: Tesseract OCR on title block")
    from services.ocr_title import extract_title_block_meta
    ocr_meta = extract_title_block_meta(title_crop)
    logger.info(f"  OCR meta: {ocr_meta}")

    # ── Steps 3 & 4: Gemini extraction ───────────────────────────────────────
    if not settings.has_api_key:
        logger.warning("No GEMINI_API_KEY — using mock pipeline")
        mock = generate_mock_mto(filename=file_path.name)
        mock.source = "mock"
        return mock

    logger.info("Step 3: Gemini Pass A (full image)")
    from services.gemini_client import pass_a_extract, pass_b_extract
    try:
        pass_a = pass_a_extract(full_bytes)
        logger.info(f"  Pass A: {len(pass_a.get('items', []))} items, meta={pass_a.get('drawing_meta', {})}")
    except MissingAPIKeyError:
        logger.warning("Missing API key — using mock")
        mock = generate_mock_mto(filename=file_path.name)
        mock.source = "mock"
        return mock

    logger.info("Step 4: Gemini Pass B (BOM region)")
    try:
        pass_b = pass_b_extract(bom_bytes)
        logger.info(f"  Pass B: {len(pass_b.get('bom_rows', []))} rows, conf={pass_b.get('confidence')}")
    except Exception as e:
        logger.error(f"  Pass B FAILED: {e}\n{traceback.format_exc()}")
        pass_b = {"bom_rows": [], "confidence": 0.0}  # Degrade gracefully for Pass B only if Pass A succeeded

    # ── Step 5: Reconciliation ────────────────────────────────────────────────
    logger.info("Step 5: Reconciliation")
    from services.reconciliation import reconcile
    drawing_meta, items, summary = reconcile(pass_a, pass_b, ocr_meta)
    logger.info(f"  Reconciled: {len(items)} items, pipe={summary.total_pipe_length_m}m")

    # If Gemini returned nothing useful, raise an error instead of falling back silently
    if not items:
        raise ValueError("AI extraction yielded 0 items. Please check if the drawing is valid or if the AI failed to generate correct JSON.")

    return MTOResult(
        drawing_meta=drawing_meta,
        items=items,
        summary=summary,
        source="ai",
        processing_time_s=None,  # set by caller
    )
